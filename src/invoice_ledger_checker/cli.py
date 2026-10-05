"""invoice-ledger 命令行入口。

骨架期可用命令：
- demo    内置合成演示数据走通 解析外全链路（台账入库 -> 规则引擎 -> 异常清单）
- doctor  可选依赖体检（extras 覆盖自检）
- --version

未交付命令（generate/parse/check/export/app）打印所属里程碑后退出码 2，
不做半成品假实现。设计契约：plan/03 §2 目录结构、plan/05 §2 里程碑。
"""

import argparse
import sys
from typing import List, Optional

from . import __version__
from .models import Evidence, InvoiceCard, LineItem
from .storage import Ledger
from .utils import OptionalDependencyError, force_utf8_stdio

# 未交付命令 -> (所属里程碑, 一句话说明)
_STUB_COMMANDS = {
    "generate": ("M1 数据先行", "合成发票生成器（固定 seed + 真值 JSON）"),
    "parse": ("M2 解析层", "数电票 XML / 版式 PDF 批量解析为发票参数卡"),
    "check": ("M3 规则引擎", "对台账执行八类异常检测规则"),
    "export": ("M5 桌面交付", "Excel 台账导出（openpyxl，条件格式标红）"),
    "app": ("M5 桌面交付", "PySide6 桌面应用（导入/台账/看板/异常清单）"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="invoice-ledger",
        description="电子发票智能台账与重复报销检测（全离线，规则引擎为主）",
    )
    parser.add_argument(
        "--version", action="version", version="invoice-ledger " + __version__
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.add_parser("demo", help="内置合成演示：入库+查重+算术复核全链路（骨架可用）")
    sub.add_parser("doctor", help="可选依赖体检：报告各 extras 组件可用性")
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


def _cmd_demo() -> int:
    """内置演示：三张合成卡入库（一张重复）+ 引擎检测出 2 条异常。

    全部数据为程序合成虚构，无任何真实主体；种子规则 R-ARITH-01/R-DUP-01
    为骨架交付，M3 全量八规则后本命令同步升级为端到端演示。
    """
    from .rules import DetectionEngine, register_builtin

    cards = _demo_cards()
    ledger = Ledger(":memory:")
    ledger.create_batch("batch-demo-001", source_desc="内置演示", file_count=3)
    accepted, rejected = 0, []
    for card in cards:
        if ledger.add_invoice(card, "batch-demo-001"):
            accepted += 1
        else:
            rejected.append(card.invoice_number)

    engine = DetectionEngine()
    register_builtin(engine)
    findings = engine.run(cards)
    for finding in findings:
        ledger.add_finding(finding.to_dict(), batch_id="batch-demo-001")

    print("invoice-ledger demo（数据全部为合成虚构）")
    print("-" * 56)
    print("导入：3 张合成发票 -> 台账入库 %d 张，重复拒收 %d 张 %s"
          % (accepted, len(rejected), rejected or ""))
    print("台账总数：%d（SQLite 内存库）" % ledger.count_invoices())
    print("规则引擎：注册 %s，产出异常 %d 条"
          % ("/".join(engine.rule_ids), len(findings)))
    for finding in findings:
        print("  [%s] %s %s" % (finding.level, finding.rule_id, finding.message))
    print("findings 持久化：%d 条" % len(ledger.list_findings()))
    print("-" * 56)
    print("下一步：generate(M1) -> parse(M2) -> check(M3) 全量规则；见 plan/05 里程碑")
    return 0


def _demo_cards() -> List[InvoiceCard]:
    """演示用合成发票卡（税号为 DEMO 假格式，与真实统一社会信用代码无涉）。"""
    common = dict(
        buyer_name="星辰科技有限公司",
        buyer_tax_id="91330100DEMOFAKE01",
        confidence=1.0,
    )
    card1 = InvoiceCard(
        invoice_number="25910000000000123456",
        invoice_type="数电普票",
        issue_date="2026-01-05",
        seller_name="云图商贸有限公司",
        seller_tax_id="91330100DEMOFAKE02",
        items=[LineItem(name="会议服务费", amount="1000.00", tax_rate="0.13", tax_amount="130.00")],
        amount="1000.00",
        tax_amount="130.00",
        total_with_tax="1130.00",
        total_with_tax_cn="壹仟壹佰叁拾元整",
        evidence=[Evidence(source_file="demo/25910000000000123456.xml", quote="<TotalAmount>1130.00", location="/Invoice/TotalAmount")],
        **common,
    )
    card2 = InvoiceCard(
        invoice_number="25910000000000123457",
        invoice_type="数电专票",
        issue_date="2026-01-06",
        buyer_name="云图商贸有限公司",
        buyer_tax_id="91330100DEMOFAKE02",
        seller_name="星辰科技有限公司",
        seller_tax_id="91330100DEMOFAKE01",
        items=[LineItem(name="咨询服务费", amount="2000.00", tax_rate="0.06", tax_amount="120.00")],
        amount="2000.00",
        tax_amount="120.00",
        total_with_tax="2180.00",  # 注入算术错误：应为 2120.00
        total_with_tax_cn="贰仟壹佰贰拾元整",
        evidence=[Evidence(source_file="demo/25910000000000123457.xml", quote="<TotalAmount>2180.00", location="/Invoice/TotalAmount")],
        confidence=1.0,
    )
    card3 = InvoiceCard.from_dict(card1.to_dict())  # 与 card1 同号：模拟跨批次重复报销
    card3.evidence = [Evidence(source_file="demo_retry/25910000000000123456.xml", quote="<TotalAmount>1130.00", location="/Invoice/TotalAmount")]
    return [card1, card2, card3]


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
