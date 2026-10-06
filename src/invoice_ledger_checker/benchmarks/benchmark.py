"""内置评测基准（M4 交付；口径权威 plan/05 §3 + generator/synthetic.py 模块注释）。

两条基准 + 门槛断言 + 确定性报告：

- 字段解析基准：冻结 60 份（OFD 3 份顺延不解析、显式登记）逐文件"完美解析器"
  真值卡（cards.json）vs 解析卡 dict **字段级**对账——复用 field_match.flatten_card
  同一实现（items 展开为 items[i].field；evidence/confidence/field_flags/batch_id
  不参与；空==空计正确），输出微平均（全字段聚总）+ 宏平均（分字段 P/R/F1 再平均）
  + 分字段表；逐文件 P/R/F1 与 field_match.compare 的一致性由内部断言守门。
- 异常检测基准：八规则引擎（--anchor-manifest 同款基准通路：批次 expense_anchor、
  existing_numbers 空集=新库语义）vs expectations.json 的 expect ∪ also_expect
  全集，按 (号码, rule_id) 对账、级别并入三元组：
  检出率 = TP/真值异常、误报率 = FP/全部告警、判定准确率 = 级别一致三元组/真值异常。
- 零 API 可重复：纯规则通路、固定输入、无墙钟——R-TIME 只走 manifest 批次
  anchor（缺映射批次记 anchors_missing 并列为门槛失败，禁用导入时刻兜底），
  报告不含时间戳/路径/环境信息，同输入重跑逐字节一致（守门测试断言）。

门槛（plan/05 §2 M4 行）：解析宏平均 F1 >= 0.95、检出率 = 100%、误报 = 0、
判定准确率 = 100%。任一未达 -> benchmark 命令退出码 1（回归信号）。
"""

import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from .field_match import compare, flatten_card

# 门槛常量（plan/05 §2 M4 行 + §3 基准口径；改门槛先改 plan/05）
PARSE_F1_MIN = 0.95
DETECTION_RATE_MIN = 1.0
FALSE_POSITIVE_RATE_MAX = 0.0
LEVEL_ACCURACY_MIN = 1.0

# 零容忍项（冻结基准的结构完整性，不属于容差指标）
_ITEMS_KEY_RE = re.compile(r"^items\[\d+\]\.")


def _norm_key(key: str) -> str:
    """items[3].name -> items[*].name（分字段表按字段聚合，与行号无关）。"""
    return _ITEMS_KEY_RE.sub("items[*].", key)


def _field_sort_key(key: str) -> Tuple[int, str]:
    """卡级字段在前、明细行字段在后，组内按名称序（表格稳定可读）。"""
    return (1 if key.startswith("items[") else 0, key)


def _ratio(numerator: int, denominator: int) -> float:
    """P/R 惯例：分母为 0 记 1.0（与 field_match.compare 一致）。"""
    return numerator / denominator if denominator else 1.0


def _load_json(data_dir: str, name: str) -> Any:
    with open(os.path.join(data_dir, "ground_truth", name), encoding="utf-8") as fh:
        return json.load(fh)


def _parse_frozen_cards(data_dir: str, manifest: Dict[str, Any]
                        ) -> List[Tuple[str, Any, Optional[str]]]:
    """按 manifest 逐文件解析（OFD 顺延跳过）；返回 [(相对路径, 卡或 None, 错误或 None)]。

    缺可选依赖显式上抛（CLI 退出码 2），不做静默降级假绿；其余解析失败
    记 failed（字段基准按整卡漏解析计 FN，检测基准剔除该卡）。
    """
    from ..parsing import parser_for
    from ..utils import OptionalDependencyError

    out: List[Tuple[str, Any, Optional[str]]] = []
    for record in manifest["files"]:
        rel_path = record["path"]
        if record["format"] == "ofd":
            continue  # P2 顺延：不解析、显式登记（OFD 号码无规则期望，无结构缺口）
        card = None
        error = None
        parser = parser_for("." + record["format"])
        if parser is None:
            error = "不支持的格式 .%s" % record["format"]
        else:
            try:
                card = parser(os.path.join(data_dir, rel_path.replace("/", os.sep)))
                card.batch_id = record["batch_id"]
            except OptionalDependencyError:
                raise
            except Exception as exc:  # 冻结数据不应失败；失败即门槛信号
                error = "%s: %s" % (type(exc).__name__, exc)
        out.append((rel_path, card, error))
    return out


# ---------------------------------------------------------------- 字段解析基准


def _field_metrics(data_dir: str, manifest: Dict[str, Any],
                   parsed_files: List[Tuple[str, Any, Optional[str]]]
                   ) -> Dict[str, Any]:
    """字段级对账：微平均 + 宏平均 + 分字段表（口径 = field_match.compare）。"""
    truth_cards = _load_json(data_dir, "cards.json")
    per_field: Dict[str, Dict[str, int]] = {}
    mismatches: List[Dict[str, str]] = []
    deferred_ofd: List[str] = []
    failed_files: List[Dict[str, str]] = []
    micro = {"tp": 0, "fp": 0, "fn": 0}
    parsed_count = 0

    for record in manifest["files"]:
        if record["format"] == "ofd":
            deferred_ofd.append(record["path"])

    for rel_path, card, error in parsed_files:
        truth = truth_cards.get(rel_path)
        if truth is None:
            raise RuntimeError("cards.json 缺少真值卡: %s" % rel_path)
        parsed_card: Dict[str, Any] = {}
        if card is None:
            failed_files.append({"path": rel_path, "error": error or "解析失败"})
        else:
            parsed_card = card.to_dict()
            parsed_count += 1

        n_items = max(len(truth.get("items") or []), len(parsed_card.get("items") or []))
        truth_flat = flatten_card(truth, n_items)
        parsed_flat = flatten_card(parsed_card, n_items)
        file_tp = file_fp = file_fn = 0
        for key in sorted(set(truth_flat) | set(parsed_flat)):
            expected = truth_flat.get(key)
            actual = parsed_flat.get(key)
            bucket = per_field.setdefault(_norm_key(key), {"tp": 0, "fp": 0, "fn": 0})
            if expected == actual:
                file_tp += 1
                bucket["tp"] += 1
                micro["tp"] += 1
            elif expected is None:
                file_fp += 1
                bucket["fp"] += 1
                micro["fp"] += 1
            elif actual is None:
                file_fn += 1
                bucket["fn"] += 1
                micro["fn"] += 1
            else:
                file_fp += 1
                file_fn += 1
                bucket["fp"] += 1
                bucket["fn"] += 1
                micro["fp"] += 1
                micro["fn"] += 1
                mismatches.append({"path": rel_path, "field": key,
                                   "expected": expected, "actual": actual})

        # 同口径守门：逐文件 P/R/F1 必须与 field_match.compare 一致（防两套判定漂移）
        ref = compare(truth, parsed_card)
        mine_p = _ratio(file_tp, file_tp + file_fp)
        mine_r = _ratio(file_tp, file_tp + file_fn)
        mine_f1 = 2 * mine_p * mine_r / (mine_p + mine_r) if mine_p + mine_r else 1.0
        if any(abs(a - b) > 1e-9 for a, b in
               ((mine_p, ref["precision"]), (mine_r, ref["recall"]), (mine_f1, ref["f1"]))):
            raise RuntimeError("字段对账口径与 field_match.compare 漂移: %s" % rel_path)

    fields_out: List[Dict[str, Any]] = []
    for key in sorted(per_field, key=_field_sort_key):
        counts = per_field[key]
        p = _ratio(counts["tp"], counts["tp"] + counts["fp"])
        r = _ratio(counts["tp"], counts["tp"] + counts["fn"])
        f1 = 2 * p * r / (p + r) if p + r else 1.0
        fields_out.append({"field": key, "tp": counts["tp"], "fp": counts["fp"],
                           "fn": counts["fn"], "precision": p, "recall": r, "f1": f1})
    if fields_out:
        macro = {
            "precision": sum(f["precision"] for f in fields_out) / len(fields_out),
            "recall": sum(f["recall"] for f in fields_out) / len(fields_out),
            "f1": sum(f["f1"] for f in fields_out) / len(fields_out),
        }
    else:
        macro = {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    micro_metrics = {
        "precision": _ratio(micro["tp"], micro["tp"] + micro["fp"]),
        "recall": _ratio(micro["tp"], micro["tp"] + micro["fn"]),
    }
    p, r = micro_metrics["precision"], micro_metrics["recall"]
    micro_metrics["f1"] = 2 * p * r / (p + r) if p + r else 1.0

    return {
        "files_total": len(manifest["files"]),
        "parsed_count": parsed_count,
        "deferred_ofd": deferred_ofd,
        "failed_files": failed_files,
        "micro": micro_metrics,
        "macro": macro,
        "fields": fields_out,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------- 异常检测基准


def _detection_metrics(data_dir: str, manifest: Dict[str, Any],
                       parsed_files: List[Tuple[str, Any, Optional[str]]]
                       ) -> Dict[str, Any]:
    """八规则引擎 vs expect ∪ also_expect 全集（对账语义权威 generator/synthetic.py §2）。"""
    from ..rules import DetectionEngine, register_builtin

    expectations = _load_json(data_dir, "expectations.json")
    anchors = {b["batch_id"]: b["expense_anchor"] for b in manifest.get("batches", [])}
    cards = [card for _, card, _ in parsed_files if card is not None]
    anchors_missing = sorted({card.batch_id for card in cards} - set(anchors))

    # 基准通路（与 check --anchor-manifest 同款）；existing_numbers 空集 = 新库语义；
    # 不传 default_anchor——缺映射批次由 anchors_missing 门槛兜住，禁用墙钟兜底。
    engine = DetectionEngine()
    register_builtin(engine)
    findings = engine.run(cards, {"batch_anchors": anchors, "existing_numbers": set()})

    truth_triples = set()
    for number, entry in expectations.items():
        for rule_id, level in (list(entry.get("expect", {}).items())
                               + list(entry.get("also_expect", {}).items())):
            truth_triples.add((number, rule_id, level))
    alert_triples = set()
    for finding in findings:
        for number in finding.invoice_numbers:
            alert_triples.add((number, finding.rule_id, finding.level))

    truth_pairs = {(n, r) for n, r, _ in truth_triples}
    alert_pairs = {(n, r) for n, r, _ in alert_triples}
    tp_pairs = truth_pairs & alert_pairs
    fp_pairs = alert_pairs - truth_pairs
    fn_pairs = truth_pairs - alert_pairs
    level_ok = truth_triples & alert_triples  # 级别一致的三元组

    return {
        "anchors_missing": anchors_missing,
        "cards_total": len(cards),
        "numbers_expected": len(expectations),
        "truth_anomalies": len(truth_pairs),
        "alerts": len(alert_pairs),
        "tp": len(tp_pairs),
        "fp": len(fp_pairs),
        "fn": len(fn_pairs),
        "level_mismatch": len(tp_pairs) - len(level_ok),
        "detection_rate": _ratio(len(tp_pairs), len(truth_pairs)),
        "false_positive_rate": (len(fp_pairs) / len(alert_pairs)) if alert_pairs else 0.0,
        "level_accuracy": _ratio(len(level_ok), len(truth_pairs)),
        "findings_total": len(findings),
        "findings_shape": sorted(
            (rule_id, level, count)
            for (rule_id, level), count in
            Counter((f.rule_id, f.level) for f in findings).items()),
        "unknown_numbers": sorted({n for n, _, _ in alert_triples if n not in expectations}),
    }


# ---------------------------------------------------------------- 门槛与总入口


def gate_failures(metrics: Dict[str, Any]) -> List[str]:
    """门槛断言（plan/05 §2 M4 行）：返回未达项清单，空 = 全部通过。"""
    parse = metrics["parse"]
    detect = metrics["detect"]
    failures: List[str] = []
    if parse["failed_files"]:
        failures.append("冻结数据解析失败 %d 个（%s...）——字段基准已按整卡漏解析计 FN"
                        % (len(parse["failed_files"]), parse["failed_files"][0]["path"]))
    if parse["macro"]["f1"] < PARSE_F1_MIN:
        failures.append("解析宏平均 F1 %.4f < 门槛 %.2f"
                        % (parse["macro"]["f1"], PARSE_F1_MIN))
    if parse["mismatches"]:
        failures.append("字段级不一致 %d 处（%s ...）"
                        % (len(parse["mismatches"]), parse["mismatches"][0]["path"]))
    if detect["detection_rate"] < DETECTION_RATE_MIN:
        failures.append("检出率 %.2f%% < 门槛 100%%（FN %d 条）"
                        % (100 * detect["detection_rate"], detect["fn"]))
    if detect["false_positive_rate"] > FALSE_POSITIVE_RATE_MAX:
        failures.append("误报率 %.2f%% > 门槛 0%%（FP %d 条）"
                        % (100 * detect["false_positive_rate"], detect["fp"]))
    if detect["level_accuracy"] < LEVEL_ACCURACY_MIN:
        failures.append("判定准确率 %.2f%% < 门槛 100%%（级别不符 %d 条）"
                        % (100 * detect["level_accuracy"], detect["level_mismatch"]))
    if detect["unknown_numbers"]:
        failures.append("引擎对真值之外的号码产生告警 %d 个：%s"
                        % (len(detect["unknown_numbers"]),
                           "、".join(detect["unknown_numbers"][:3])))
    if metrics["anchors_missing"]:
        failures.append("批次缺 expense_anchor 映射（墙钟兜底禁用）：%s"
                        % "、".join(metrics["anchors_missing"]))
    return failures


def run_benchmark(data_dir: str) -> Dict[str, Any]:
    """跑两条基准，返回指标字典（含门槛输入；不落盘、不打印）。"""
    manifest = _load_json(data_dir, "manifest.json")
    parsed_files = _parse_frozen_cards(data_dir, manifest)
    parse_metrics = _field_metrics(data_dir, manifest, parsed_files)
    detect_metrics = _detection_metrics(data_dir, manifest, parsed_files)
    anchors_missing = detect_metrics.pop("anchors_missing")
    return {
        "manifest": {
            "seed": manifest.get("seed"),
            "n": manifest.get("n"),
            "anomaly_rate": manifest.get("anomaly_rate"),
            "by_format": manifest.get("counts", {}).get("by_format", {}),
            "batches": manifest.get("batches", []),
        },
        "parse": parse_metrics,
        "detect": detect_metrics,
        "anchors_missing": anchors_missing,
    }


# ---------------------------------------------------------------- 确定性报告


def _fmt4(value: float) -> str:
    return "%.4f" % value


def _pct(value: float) -> str:
    return "%.2f%%" % (100 * value)


def write_report(metrics: Dict[str, Any], path: str) -> str:
    """指标 -> Markdown 报告；内容只由输入数据与结果决定（无墙钟/路径/环境）。

    同输入重跑逐字节一致（LF 行尾，与 .gitattributes eol=lf 一致）。
    """
    parse = metrics["parse"]
    detect = metrics["detect"]
    man = metrics["manifest"]
    gate = gate_failures(metrics)

    lines: List[str] = []
    add = lines.append
    add("# 内置评测基准报告（M4 生成物）")
    add("")
    add("> 由 `py -m invoice_ledger_checker benchmark` 生成；零 API 可重复——纯规则通路、")
    add("> 固定输入（冻结数据 + manifest 批次 expense_anchor）、无墙钟，同输入重跑本文件")
    add("> 逐字节一致（守门测试断言）。口径权威：plan/05 §3 与 generator/synthetic.py")
    add("> 模块注释；字段级对账复用包内 [field_match.py]"
        "(../src/invoice_ledger_checker/benchmarks/field_match.py) 同一实现。")
    add("")
    add("## 1. 数据概览")
    add("")
    add("| 项 | 值 |")
    add("|---|---|")
    add("| seed / n / anomaly_rate | %s / %s / %s |" % (man["seed"], man["n"], man["anomaly_rate"]))
    add("| 格式分布 | %s |" % " / ".join("%s %d" % (fmt, man["by_format"][fmt])
                                       for fmt in sorted(man["by_format"])))
    add("| 批次 | %s |" % "；".join(
        "%s（anchor %s，%d 文件）" % (b["batch_id"], b["expense_anchor"], b["file_count"])
        for b in man["batches"]))
    add("| 解析 | 成功 %d / %d（OFD 顺延 %d 份 P2 不参与指标，失败 %d） |"
        % (parse["parsed_count"], parse["files_total"], len(parse["deferred_ofd"]),
           len(parse["failed_files"])))
    if parse["failed_files"]:
        add("| 解析失败清单 | %s |" % "；".join(
            "%s（%s）" % (f["path"], f["error"]) for f in parse["failed_files"]))
    add("")
    add("### OFD 顺延登记（P2 加分项未交付，显式登记）")
    add("")
    for rel_path in parse["deferred_ofd"]:
        add("- `%s`" % rel_path)
    add("")
    add("OFD 顺延号码不挂任何规则期望（对真值全集对账无结构性缺口，"
        "tests/test_baseline_detection.py 守门）。")
    add("")
    add("## 2. 字段解析基准（冻结数据 vs cards.json，字段级）")
    add("")
    add("| 口径 | P | R | F1 |")
    add("|---|---|---|---|")
    add("| 微平均（全字段聚总） | %s | %s | %s |"
        % (_fmt4(parse["micro"]["precision"]), _fmt4(parse["micro"]["recall"]),
           _fmt4(parse["micro"]["f1"])))
    add("| 宏平均（分字段再平均，门槛 %.2f） | %s | %s | %s |"
        % (PARSE_F1_MIN, _fmt4(parse["macro"]["precision"]),
           _fmt4(parse["macro"]["recall"]), _fmt4(parse["macro"]["f1"])))
    add("")
    add("分字段表（items[*] 为明细行字段按行聚合；空==空计正确，口径同 field_match.py）：")
    add("")
    add("| 字段 | TP | FP | FN | P | R | F1 |")
    add("|---|---|---|---|---|---|---|")
    for f in parse["fields"]:
        add("| %s | %d | %d | %d | %s | %s | %s |"
            % (f["field"], f["tp"], f["fp"], f["fn"], _fmt4(f["precision"]),
               _fmt4(f["recall"]), _fmt4(f["f1"])))
    add("")
    if parse["mismatches"]:
        add("不一致清单（真值 vs 解析）：")
        add("")
        for m in parse["mismatches"]:
            add("- `%s` %s：期望 %r，实际 %r" % (m["path"], m["field"],
                                              m["expected"], m["actual"]))
    else:
        add("不一致清单：无。")
    add("")
    add("## 3. 异常检测基准（八规则 vs expect ∪ also_expect 全集）")
    add("")
    add("对账语义：引擎 Finding 按发票号码展开为 (号码, rule_id) 对与真值全集对拍——"
        "多记=误报、少记=漏报、级别不符=错判；时间基准 = manifest 批次 "
        "expense_anchor（基准通路，与墙钟无关）。")
    add("")
    add("| 指标 | 值 |")
    add("|---|---|")
    add("| 真值异常（expect ∪ also_expect 对数） | %d |" % detect["truth_anomalies"])
    add("| 引擎告警（按号码展开） | %d（%d 条 finding） |"
        % (detect["alerts"], detect["findings_total"]))
    add("| TP / FP / FN / 级别不符 | %d / %d / %d / %d |"
        % (detect["tp"], detect["fp"], detect["fn"], detect["level_mismatch"]))
    add("| 检出率（TP/真值异常） | %s |" % _pct(detect["detection_rate"]))
    add("| 误报率（FP/全部告警） | %s |" % _pct(detect["false_positive_rate"]))
    add("| 判定准确率（级别一致/真值异常） | %s |" % _pct(detect["level_accuracy"]))
    add("")
    add("finding 形态（rule_id × 级别 × 条数）：")
    add("")
    add("| rule_id | 级别 | 条数 |")
    add("|---|---|---|")
    for rule_id, level, count in detect["findings_shape"]:
        add("| %s | %s | %d |" % (rule_id, level, count))
    add("")
    add("## 4. 门槛断言（plan/05 §2 M4 行）")
    add("")
    add("| 门槛 | 要求 | 实测 | 结果 |")
    add("|---|---|---|---|")
    add("| 解析宏平均 F1 | >= %s | %s | %s |"
        % (_fmt4(PARSE_F1_MIN), _fmt4(parse["macro"]["f1"]),
           "通过" if parse["macro"]["f1"] >= PARSE_F1_MIN else "**未通过**"))
    add("| 检出率 | = 100%% | %s | %s |"
        % (_pct(detect["detection_rate"]),
           "通过" if detect["detection_rate"] >= DETECTION_RATE_MIN else "**未通过**"))
    add("| 误报率 | = 0%% | %s | %s |"
        % (_pct(detect["false_positive_rate"]),
           "通过" if detect["false_positive_rate"] <= FALSE_POSITIVE_RATE_MAX else "**未通过**"))
    add("| 判定准确率 | = 100%% | %s | %s |"
        % (_pct(detect["level_accuracy"]),
           "通过" if detect["level_accuracy"] >= LEVEL_ACCURACY_MIN else "**未通过**"))
    add("| 冻结数据解析失败 | = 0 | %d | %s |"
        % (len(parse["failed_files"]),
           "通过" if not parse["failed_files"] else "**未通过**"))
    add("| 未知号码告警 | = 0 | %d | %s |"
        % (len(detect["unknown_numbers"]),
           "通过" if not detect["unknown_numbers"] else "**未通过**"))
    add("| 批次锚点覆盖（禁墙钟兜底） | 全部 | %d/%d | %s |"
        % (len(man["batches"]) - len(metrics["anchors_missing"]), len(man["batches"]),
           "通过" if not metrics["anchors_missing"] else "**未通过**"))
    add("")
    if gate:
        add("**门槛未达（退出码 1，回归信号）**：")
        add("")
        for item in gate:
            add("- %s" % item)
    else:
        add("全部门槛通过。")
    add("")
    add("## 5. 复现")
    add("")
    add("```bash")
    add("py -m invoice_ledger_checker generate --out data --seed 42 --n 60"
        "   # 冻结数据重建（位级一致）")
    add("py -m invoice_ledger_checker benchmark"
        "                              # 本报告一键重跑")
    add("py -m pytest"
        "                                                      # 测试形态基准同源回归")
    add("```")
    add("")
    add("> 回归纪律：改数据/改规则/改接口后必须重跑本基准确认不回退"
        "（门槛未达退出码 1）。")
    add("")

    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    return path
