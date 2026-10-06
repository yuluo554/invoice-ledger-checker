"""invoice-ledger 命令行入口。

可用命令：
- demo      端到端演示：合成数据 -> 解析 -> 入库 -> 八规则检测（M3 起）
- doctor    可选依赖体检（extras 覆盖自检）
- generate  合成发票数据集 + 真值 JSON（M1 交付；数据全虚构）
- parse     批量解析发票文件为发票参数卡并出导入报告（M2 交付）
- check     解析 -> SQLite 台账入库 -> 八规则检测 -> 三级异常清单（M3 交付）
- --version

未交付命令（export/app）打印所属里程碑后退出码 2，不做半成品假实现。
设计契约：plan/03 §2 目录结构、plan/05 §2 里程碑。
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from . import __version__
from .models import InvoiceCard
from .storage import Ledger
from .utils import OptionalDependencyError, force_utf8_stdio

# 未交付命令 -> (所属里程碑, 一句话说明)
_STUB_COMMANDS = {
    "export": ("M5 桌面交付", "Excel 台账导出（openpyxl，条件格式标红）"),
    "app": ("M5 桌面交付", "PySide6 桌面应用（导入/台账/看板/异常清单）"),
}

_LEVEL_ORDER = ("error", "suspicious", "review")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invoice-ledger",
        description="电子发票智能台账与重复报销检测（全离线，规则引擎为主）",
    )
    parser.add_argument(
        "--version", action="version", version="invoice-ledger " + __version__
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.add_parser("demo", help="端到端演示：合成数据->解析->入库->八规则检测（M3）")
    sub.add_parser("doctor", help="可选依赖体检：报告各 extras 组件可用性")
    gen = sub.add_parser(
        "generate", help="合成发票数据集 + 真值 JSON（M1 交付；数据全虚构）")
    gen.add_argument("--out", default="data", help="输出根目录（默认 data）")
    gen.add_argument("--seed", type=int, default=42, help="随机种子（默认 42）")
    gen.add_argument("--n", type=int, default=60, help="生成发票文件数（默认 60）")
    gen.add_argument("--anomaly-rate", dest="anomaly_rate", type=float, default=0.35,
                     help="注入异常的文件占比（默认 0.35）")
    gen.add_argument("--formats", default="xml,pdf,ofd",
                     help="输出格式逗号分隔，须含 xml（默认 xml,pdf,ofd）")
    par = sub.add_parser(
        "parse", help="批量解析发票文件为发票参数卡（M2 交付；批次=一级子目录名）")
    par.add_argument("directory", help="发票文件根目录（递归扫描）")
    par.add_argument("--report", action="store_true",
                     help="输出详细报告（批次/格式成功数、坏文件清单、OFD 顺延登记）")
    chk = sub.add_parser(
        "check", help="解析->台账入库->八规则检测->三级异常清单（M3 交付）")
    chk.add_argument("directory", help="发票文件根目录（递归扫描，批次=一级子目录名）")
    chk.add_argument("--db", default="ledger.db", help="SQLite 台账路径（默认 ledger.db）")
    chk.add_argument("--anchor-manifest", dest="anchor_manifest", default="",
                     help="基准通路：manifest.json 路径，批次报销基准日取 expense_anchor；"
                          "缺省为常规通路（anchor=导入时刻）")
    for name, (milestone, desc) in sorted(_STUB_COMMANDS.items()):
        sub.add_parser(name, help="[%s 未交付] %s" % (milestone, desc))
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    force_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    try:
        if args.command == "demo":
            return _cmd_demo()
        if args.command == "doctor":
            return _cmd_doctor()
        if args.command == "generate":
            return _cmd_generate(args)
        if args.command == "parse":
            return _cmd_parse(args)
        if args.command == "check":
            return _cmd_check(args)
        return _cmd_stub(args.command)
    except OptionalDependencyError as exc:
        print("[缺少依赖] %s" % exc)
        return 2
    except NotImplementedError as exc:
        print("[未实现] %s" % exc)
        return 2


def _cmd_stub(command: str) -> int:
    milestone, desc = _STUB_COMMANDS[command]
    print("命令 %r 尚未实现：%s" % (command, desc))
    print("所属里程碑：%s（路线图见 plan/05-数据计划与里程碑.md）" % milestone)
    return 2


# ---------------------------------------------------------------- 扫描与解析


def _scan_and_parse(root: str) -> Dict[str, Any]:
    """递归扫描目录并逐文件解析（parse/check 共用，M3 抽取）。

    批次 = 一级子目录名（根级文件批次 = 根目录名）。坏文件记拒绝清单不
    中断；OFD 顺延登记（P2）；缺依赖文件单列。返回结构化结果，卡片已填
    batch_id（入库与判重分离的前提，plan/04 §3.1）。
    """
    from .parsing import SUPPORTED_SUFFIXES, ParserError, parser_for

    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if os.path.splitext(name)[1].lower() in SUPPORTED_SUFFIXES:
                files.append(os.path.join(dirpath, name))

    ok_by_format: Dict[str, int] = {}
    rejected: List[Tuple[str, str]] = []   # (relpath, 原因)——内容级坏文件
    deferred_ofd: List[str] = []           # P2 顺延登记
    dep_blocked: List[str] = []            # 缺依赖未解析
    batches: Dict[str, Dict[str, int]] = {}
    cards: List[InvoiceCard] = []
    for abs_path in files:
        rel_path = os.path.relpath(abs_path, root).replace(os.sep, "/")
        parts = rel_path.split("/")
        batch_id = parts[0] if len(parts) > 1 \
            else os.path.basename(os.path.abspath(root))
        fmt = parts[-1].rsplit(".", 1)[-1].lower()
        batches.setdefault(batch_id, {"ok": 0, "rejected": 0, "deferred": 0})
        if fmt == "ofd":
            deferred_ofd.append(rel_path)
            batches[batch_id]["deferred"] += 1
            continue
        parser = parser_for("." + fmt)
        if parser is None:
            rejected.append((rel_path, "不支持的格式 .%s" % fmt))
            batches[batch_id]["rejected"] += 1
            continue
        try:
            card = parser(abs_path)
        except ParserError as exc:
            rejected.append((rel_path, str(exc)))
            batches[batch_id]["rejected"] += 1
            continue
        except OptionalDependencyError:
            dep_blocked.append(rel_path)
            batches[batch_id]["rejected"] += 1
            continue
        card.batch_id = batch_id
        ok_by_format[fmt] = ok_by_format.get(fmt, 0) + 1
        batches[batch_id]["ok"] += 1
        cards.append(card)

    return {
        "root": root,
        "files": files,
        "cards": cards,
        "ok_by_format": ok_by_format,
        "batches": batches,
        "rejected": rejected,
        "deferred_ofd": deferred_ofd,
        "dep_blocked": dep_blocked,
    }


def _print_scan_report(result: Dict[str, Any]) -> None:
    root = result["root"]
    print("输入: %s（批次=一级子目录名）" % root)
    print("扫描: %d 个发票文件，成功解析 %d 张卡"
          % (len(result["files"]), len(result["cards"])))
    for fmt in sorted(result["ok_by_format"]):
        print("  %s 成功 %d" % (fmt, result["ok_by_format"][fmt]))
    for batch_id in sorted(result["batches"]):
        stat = result["batches"][batch_id]
        print("  批次 %s: 成功 %d / 失败 %d / OFD 顺延 %d"
              % (batch_id, stat["ok"], stat["rejected"], stat["deferred"]))
    if result["deferred_ofd"]:
        print("OFD 顺延登记: %d 个文件未解析（OFD 解析器为 P2 加分项，"
              "当前版本未交付）" % len(result["deferred_ofd"]))
    if result["rejected"]:
        print("拒绝清单: %d 个" % len(result["rejected"]))
        for rel_path, reason in result["rejected"]:
            print("  %s — %s" % (rel_path, reason))
    else:
        print("拒绝清单: 无")


def _require_scannable(args) -> Optional[Dict[str, Any]]:
    """parse/check 共用的目录前置校验 + 解析；不满足契约时打印并返回 None。"""
    root = args.directory
    if not os.path.isdir(root):
        print("[参数错误] 目录不存在: %s" % root)
        return None
    result = _scan_and_parse(root)
    if not result["files"]:
        from .parsing import SUPPORTED_SUFFIXES

        print("[参数错误] 目录内无可解析发票文件（支持 %s）: %s"
              % ("/".join(SUPPORTED_SUFFIXES), root))
        return None
    if result["dep_blocked"]:
        _print_scan_report(result)
        print("[缺少依赖] %d 个文件因缺少 pdfplumber 未解析，"
              "请安装后重跑：py -m pip install -e \".[parse]\""
              % len(result["dep_blocked"]))
        return None
    return result


def _cmd_parse(args) -> int:
    """批量解析：递归扫描目录，批次=一级子目录名；坏文件记拒绝日志不中断。

    退出码契约（plan/03）：目录不存在/无可解析文件/有文件因缺依赖未解析=2；
    命令跑通（坏文件属数据条件，报告登记后照常）=0。OFD 为 P2 顺延项，
    报告显式登记不计失败。同号多文件正常各出各卡（判重交台账主键/规则层）。
    入库+检测由 check 命令承接（M3）。
    """
    result = _require_scannable(args)
    if result is None:
        return 2
    print("invoice-ledger parse（解析报告）")
    print("-" * 56)
    _print_scan_report(result)
    print("-" * 56)
    if args.report:
        print("详细报告已输出（--report）。入库+八规则检测请用 check 命令。")
    return 0


# ---------------------------------------------------------------- check


def _load_anchor_manifest(path: str) -> Dict[str, str]:
    """基准通路：读生成器 manifest，取批次 -> expense_anchor 映射。"""
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    anchors = {}
    for batch in manifest.get("batches", []):
        if batch.get("batch_id") and batch.get("expense_anchor"):
            anchors[batch["batch_id"]] = batch["expense_anchor"]
    return anchors


def _run_check_pipeline(result: Dict[str, Any], ledger: Ledger,
                        batch_anchors: Dict[str, str],
                        default_anchor: str
                        ) -> Tuple[int, List[str], List[Any]]:
    """入库 -> 引擎检测（M3 定稿：入库与判重分离，plan/04 §3.1）。

    返回 (入库成功数, 主键拒收号码, findings)。引擎输入 = 全部解析卡
    （含即将被主键拒收的同号副本）；existing_numbers 取入库前台账既有
    号码集，保证跨批次/跨运行重复同样被 R-DUP-01 命中。
    """
    from .rules import DetectionEngine, register_builtin

    existing = ledger.existing_numbers()
    accepted = 0
    pk_rejected: List[str] = []
    for card in result["cards"]:
        if ledger.add_invoice(card, card.batch_id):
            accepted += 1
        else:
            pk_rejected.append(card.invoice_number)

    engine = DetectionEngine()
    register_builtin(engine)
    findings = engine.run(result["cards"], {
        "existing_numbers": existing,
        "batch_anchors": batch_anchors,
        "default_anchor": default_anchor,
    })

    batch_of: Dict[str, set] = {}
    for card in result["cards"]:
        batch_of.setdefault(card.invoice_number, set()).add(card.batch_id)
    for finding in findings:
        finding_batches: set = set()
        for number in finding.invoice_numbers:
            finding_batches.update(batch_of.get(number, ()))
        finding_batch = finding_batches.pop() if len(finding_batches) == 1 else None
        ledger.add_finding(finding.to_dict(), batch_id=finding_batch)
    return accepted, pk_rejected, findings


def _print_findings(findings) -> None:
    by_level: Dict[str, List[Any]] = {level: [] for level in _LEVEL_ORDER}
    for finding in findings:
        by_level.setdefault(finding.level, []).append(finding)
    counts = " / ".join("%s %d" % (level, len(by_level[level]))
                        for level in _LEVEL_ORDER if by_level.get(level))
    if not findings:
        print("异常清单: 无（全部规则通过）")
        return
    print("异常清单（%s）:" % counts)
    for level in _LEVEL_ORDER:
        for finding in sorted(by_level.get(level, []),
                              key=lambda f: (f.rule_id, f.invoice_numbers)):
            print("  [%s] %s %s | %s"
                  % (level, finding.rule_id,
                     ",".join(finding.invoice_numbers), finding.message))


def _cmd_check(args) -> int:
    """解析 -> 台账入库 -> 八规则检测 -> 三级异常清单落库 + stdout。

    退出码契约同 parse：目录不存在/无可解析文件/缺依赖=2；坏文件属数据
    条件照常跑通=0。R-TIME 双通路（plan/04 §3.1）：--anchor-manifest 读
    批次 expense_anchor（基准可复现）；缺省 anchor=导入时刻（当天）。
    重复检测请用新 --db 或先删旧库——重复导入本身是 R-DUP-01 异常信号，
    findings 按 finding_id 幂等拒收，不重复落库。
    """
    result = _require_scannable(args)
    if result is None:
        return 2

    import datetime

    if args.anchor_manifest:
        try:
            batch_anchors = _load_anchor_manifest(args.anchor_manifest)
        except (OSError, ValueError) as exc:
            print("[参数错误] anchor manifest 不可读: %s（%s）"
                  % (args.anchor_manifest, exc))
            return 2
        anchor_desc = "批次 expense_anchor（--anchor-manifest 基准通路）"
    else:
        batch_anchors = {}
        anchor_desc = "导入时刻（常规通路）"
    default_anchor = datetime.date.today().isoformat()

    ledger = Ledger(args.db)
    try:
        for batch_id in sorted(result["batches"]):
            stat = result["batches"][batch_id]
            log = {
                "rejected": [{"path": p, "reason": r}
                             for p, r in result["rejected"]
                             if p.split("/")[0] == batch_id],
                "deferred_ofd": [p for p in result["deferred_ofd"]
                                 if p.split("/")[0] == batch_id],
            }
            ledger.create_batch(
                batch_id,
                source_desc=result["root"],
                file_count=sum(stat.values()),
            )
            ledger.conn.execute(
                "UPDATE batches SET log_json = ? WHERE batch_id = ?",
                (json.dumps(log, ensure_ascii=False), batch_id),
            )
            ledger.conn.commit()

        accepted, pk_rejected, findings = _run_check_pipeline(
            result, ledger, batch_anchors, default_anchor)
    finally:
        ledger.close()

    print("invoice-ledger check（入库+八规则检测；合成数据不含任何真实主体）")
    print("-" * 56)
    _print_scan_report(result)
    print("台账: %s（批次 %d 个；入库 %d 张，主键拒收同号副本 %d 张）"
          % (args.db, len(result["batches"]), accepted, len(pk_rejected)))
    if pk_rejected:
        print("  主键拒收: %s" % "、".join(sorted(pk_rejected)))
    print("时间基准: %s，无映射批次回退 %s" % (anchor_desc, default_anchor))
    print("检测: 八规则全量（R-DUP-01/02/03 R-SEQ-01 R-ARITH-01/02 R-TIME-01/02），"
          "异常 %d 条" % len(findings))
    _print_findings(findings)
    print("-" * 56)
    print("findings 已落库（幂等）；台账查询/筛选与 GUI 见 M5。")
    return 0


def _cmd_generate(args) -> int:
    from .generator import generate

    formats = [f.strip().lower() for f in args.formats.split(",") if f.strip()]
    try:
        summary = generate(args.out, seed=args.seed, n=args.n,
                           anomaly_rate=args.anomaly_rate, formats=formats)
    except ValueError as exc:
        print("[参数错误] %s" % exc)
        return 2
    print("invoice-ledger generate（合成数据：公司/税号/号码全虚构）")
    print("-" * 56)
    print("输出目录: %s" % summary["out_dir"])
    print("参数: seed=%d n=%d anomaly_rate=%s formats=%s"
          % (summary["seed"], summary["n"], summary["anomaly_rate"],
             ",".join(summary["formats"])))
    print("批次: %s" % "；".join(
        "%s（报销基准日 %s，%d 个文件）" % (b["batch_id"], b["expense_anchor"],
                                        b["file_count"])
        for b in summary["batches"]))
    print("文件: %s（合计 %d）" % (
        " / ".join("%s %d" % (fmt, count)
                   for fmt, count in sorted(summary["by_format"].items())),
        summary["files"]))
    print("注入: %s；基线 %d 张" % (
        " ".join("%s×%d" % (code, count)
                 for code, count in sorted(summary["by_injection"].items())),
        summary["baseline"]))
    print("真值: %s" % "、".join(summary["truth_files"]))
    print("-" * 56)
    print("同参数重跑逐字节一致（守门测试断言）；解析/检测对账语义见生成器模块注释。")
    return 0


def _cmd_demo() -> int:
    """端到端演示（M3）：合成数据 -> 解析 -> 入库 -> 八规则检测全链路。

    临时目录生成 60 张 XML 合成票（9 类注入全触发），随后走与 check 命令
    完全相同的解析+入库+检测流水线（内存库）；时间基准取生成 manifest 的
    批次 expense_anchor（基准通路）。全部数据程序合成虚构，结束后即清理。
    """
    from .generator import generate

    tmp_dir = tempfile.mkdtemp(prefix="invoice-ledger-demo-")
    try:
        generate(tmp_dir, seed=42, n=60, formats=["xml"])
        demo_args = argparse.Namespace(
            directory=os.path.join(tmp_dir, "invoices"),
            db=":memory:",
            anchor_manifest=os.path.join(tmp_dir, "ground_truth", "manifest.json"),
        )
        result = _require_scannable(demo_args)
        if result is None:
            return 2
        batch_anchors = _load_anchor_manifest(demo_args.anchor_manifest)
        ledger = Ledger(":memory:")
        try:
            for batch_id in sorted(result["batches"]):
                ledger.create_batch(
                    batch_id,
                    source_desc="内置演示（合成数据）",
                    file_count=sum(result["batches"][batch_id].values()),
                )
            import datetime

            accepted, pk_rejected, findings = _run_check_pipeline(
                result, ledger, batch_anchors, datetime.date.today().isoformat())
        finally:
            ledger.close()

        print("invoice-ledger demo（端到端：数据全部为合成虚构）")
        print("-" * 56)
        _print_scan_report(result)
        print("台账: SQLite 内存库（批次 %d 个；入库 %d 张，主键拒收同号副本 %d 张）"
              % (len(result["batches"]), accepted, len(pk_rejected)))
        print("时间基准: 生成 manifest 批次 expense_anchor（基准通路）")
        print("检测: 八规则全量，异常 %d 条" % len(findings))
        _print_findings(findings)
        print("-" * 56)
        print("对应正式命令：generate -> parse -> check；GUI 见 M5。")
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# extras 体检表：(import 模块名, extra 组名, 用途, 交付里程碑)
_OPTIONAL_DEPS = [
    ("pdfplumber", "parse", "版式 PDF 文本层解析", "M2"),
    ("reportlab", "data", "合成发票 PDF 生成", "M1"),
    ("openpyxl", "export", "Excel 台账导出", "M5"),
    ("docx", "report", "docx 摘要报告（P2）", "M5 尾"),
    ("PySide6", "desktop", "桌面 GUI", "M5"),
    ("PySide6.Addons", "desktop", "QtCharts 看板图表", "M5"),
]


def _cmd_doctor() -> int:
    import importlib.util

    print("invoice-ledger %s 可选依赖体检（核心功能零依赖，恒可用）" % __version__)
    print("-" * 56)
    missing_any = False
    for module_name, extra, purpose, milestone in _OPTIONAL_DEPS:
        spec = importlib.util.find_spec(module_name.split(".")[0])
        installed = spec is not None
        if not installed:
            missing_any = True
        state = "已安装" if installed else "未安装"
        print("  %-8s %-14s [%s] %s（%s）"
              % (state, module_name, extra, purpose, milestone))
    print("-" * 56)
    print("一键补齐：py -m pip install -e \".[all]\"")
    if not missing_any:
        print("全部可选依赖就绪。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
