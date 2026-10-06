"""基准内检出率初核（M3）：冻结 60 份 -> 八规则引擎 vs 真值非 pass 集合对拍。

对账语义权威：generator/synthetic.py 模块注释 §2/§3——引擎 Finding 按
(发票号码, rule_id, level) 对拍 expect ∪ also_expect 全集，多记=误报、
少记=漏报、级别不符=错判。正式基准脚本 M4 落 benchmarks（本文件是
M3 的测试形态初核，DoD 见 plan/HANDOFF-M3.md §5）。

测试纪律：PDF 相关需 pdfplumber（函数内导入，未安装显式 skip，与
tests/test_parsing.py 一致）。
"""

import importlib.util
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from invoice_ledger_checker.generator.synthetic import INJECTION_EXPECTATIONS
from invoice_ledger_checker.parsing import parser_for
from invoice_ledger_checker.rules import DetectionEngine, register_builtin

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
HAS_INVOICES = (DATA_DIR / "invoices").is_dir()


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


requires_pdfplumber = pytest.mark.skipif(
    not _has_module("pdfplumber"), reason="pdfplumber 未安装（CI 无重依赖路径）")
requires_data = pytest.mark.skipif(
    not HAS_INVOICES, reason="data/invoices 冻结数据不在仓（generate 可重建）")


def _load_json(name: str):
    with open(DATA_DIR / "ground_truth" / name, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_frozen_cards():
    """按 manifest 解析全部非 OFD 冻结文件，填 batch_id（check 命令同款前提）。"""
    manifest = _load_json("manifest.json")
    cards = []
    for record in manifest["files"]:
        if record["format"] == "ofd":
            continue  # P2 顺延，与 check 命令一致
        parser = parser_for("." + record["format"])
        abs_path = str(DATA_DIR / record["path"].replace("/", os.sep))
        card = parser(abs_path)
        card.batch_id = record["batch_id"]
        cards.append(card)
    return manifest, cards


def _expected_set(entry) -> set:
    return set(entry["expect"].items()) | set(entry["also_expect"].items())


def _detected_sets(findings):
    detected = {}
    for finding in findings:
        for number in finding.invoice_numbers:
            detected.setdefault(number, set()).add((finding.rule_id, finding.level))
    return detected


@requires_data
def test_truth_expectations_align_with_generator_table():
    """真值 expectations 与生成器 INJECTION_EXPECTATIONS 同源对拍（防真值漂移）。"""
    expectations = _load_json("expectations.json")
    for number, entry in expectations.items():
        expect, also_expect = INJECTION_EXPECTATIONS[entry["injection"]]
        assert set(entry["expect"].items()) == set(expect.items()), number
        assert set(entry["also_expect"].items()) == set(also_expect.items()), number


@requires_data
def test_ofd_deferred_numbers_carry_no_rule_expectations():
    """OFD 顺延文件（P2 未解析）不得挂规则期望——否则基准对账存在结构性缺口。"""
    manifest = _load_json("manifest.json")
    expectations = _load_json("expectations.json")
    deferred = {f["invoice_number"] for f in manifest["files"] if f["format"] == "ofd"}
    assert deferred, "冻结数据应含 OFD 顺延样本"
    for number in deferred:
        assert _expected_set(expectations[number]) == set(), number


@requires_data
@requires_pdfplumber
def test_detection_baseline_full_reconciliation():
    """冻结 60 份全量检测对拍：检出率 100%、误报 0、级别全对（DoD 门槛）。"""
    manifest, cards = _parse_frozen_cards()
    assert len(cards) == 57  # 60 文件 - 3 OFD 顺延
    anchors = {b["batch_id"]: b["expense_anchor"] for b in manifest["batches"]}

    engine = DetectionEngine()
    register_builtin(engine)
    findings = engine.run(cards, {
        "batch_anchors": anchors,
        "existing_numbers": set(),
    })

    expectations = _load_json("expectations.json")
    detected = _detected_sets(findings)
    problems = []
    for number, entry in expectations.items():
        want = _expected_set(entry)
        got = detected.get(number, set())
        if want != got:
            problems.append((number, entry["injection"],
                             sorted(want - got), sorted(got - want)))
    assert not problems, "检出对拍偏差: %s" % problems[:6]
    assert set(detected) <= set(expectations)  # 无未知号码的 finding

    # 注入事件计数（每码恰 1 事件 + SEQ 簇 5 张）下的 finding 形态：
    # DUP-01×2（EXACT/JOINT 各一号）、DUP-02×1、DUP-03×1（一对双号）、
    # SEQ×1（簇 5 号一 finding）、ARITH/TIME 各×2
    counter = Counter((f.rule_id, f.level) for f in findings)
    assert counter == Counter({
        ("R-DUP-01", "error"): 2, ("R-DUP-02", "error"): 1,
        ("R-DUP-03", "suspicious"): 1, ("R-SEQ-01", "suspicious"): 1,
        ("R-ARITH-01", "error"): 2, ("R-ARITH-02", "error"): 2,
        ("R-TIME-01", "error"): 2, ("R-TIME-02", "review"): 2,
    })
    assert len(engine.rule_ids) == 8


@requires_data
@requires_pdfplumber
def test_engine_without_manifest_anchors_still_catches_dup_and_arith():
    """常规通路（无 manifest，R-TIME 失效于墙钟边界外仍可复核）下，
    与时间无关的判重/算术/连号规则结论不变（引擎输入不变量）。"""
    _, cards = _parse_frozen_cards()
    engine = DetectionEngine()
    register_builtin(engine)
    findings = engine.run(cards, {"existing_numbers": set()})
    counter = Counter(f.rule_id for f in findings)
    assert counter == Counter({
        "R-DUP-01": 2, "R-DUP-02": 1, "R-DUP-03": 1, "R-SEQ-01": 1,
        "R-ARITH-01": 2, "R-ARITH-02": 2,
    })
