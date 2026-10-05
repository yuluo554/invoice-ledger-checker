"""合成发票生成器测试：可复现守门 + 真值语义对拍 + 注入不变量（M1）。

纪律（HANDOFF 既定口径 §5）：模块级只 import stdlib+pytest；reportlab/
pdfplumber 在函数体内探测，缺失时显式 skip（防静默少跑——skip 数可见）。
真值语义权威出处：generator/synthetic.py 模块注释；期望映射直接导入
INJECTION_EXPECTATIONS 对拍，防两处口径漂移。
"""

import importlib.util
import io
import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_ledger_checker.cn_amount import encode_amount
from invoice_ledger_checker.generator import generate
from invoice_ledger_checker.generator.synthetic import (
    EVENT_UNITS,
    INJECTION_EXPECTATIONS,
    allocate_events,
)
from invoice_ledger_checker.models import InvoiceCard

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _has_module(name):
    return importlib.util.find_spec(name) is not None


def _tree_bytes(root):
    """目录 -> {posix 相对路径: bytes}。"""
    snapshot = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            snapshot[path.relative_to(root).as_posix()] = path.read_bytes()
    return snapshot


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    """默认参数（seed=42, n=60, rate=0.35）生成一次，供多数测试复用。"""
    formats = ["xml", "pdf", "ofd"] if _has_module("reportlab") else ["xml", "ofd"]
    out = tmp_path_factory.mktemp("dataset")
    summary = generate(str(out), seed=42, n=60, anomaly_rate=0.35, formats=formats)
    return {
        "out": out,
        "summary": summary,
        "formats": formats,
        "cards": json.loads((out / "ground_truth" / "cards.json").read_text("utf-8")),
        "expectations": json.loads(
            (out / "ground_truth" / "expectations.json").read_text("utf-8")),
        "manifest": json.loads(
            (out / "ground_truth" / "manifest.json").read_text("utf-8")),
    }


# ---------------------------------------------------------------- 可复现守门


def test_two_runs_byte_identical(tmp_path, dataset):
    """同 seed+参数两次生成逐字节一致（M1 DoD 守门；PDF 需 reportlab）。"""
    second = tmp_path / "second"
    generate(str(second), seed=42, n=60, anomaly_rate=0.35, formats=dataset["formats"])
    assert _tree_bytes(second) == _tree_bytes(dataset["out"])


def _assert_text_lf(root):
    """EOL 门：文本产物（loose XML/JSON + OFD 内部 XML）无 CR。

    PDF/OFD 本体是二进制容器（deflate 流天然含 0x0D 字节），git
    text=auto 对二进制不做 EOL 转换，不在门内。
    """
    for rel_path, content in _tree_bytes(root).items():
        if rel_path.endswith(".ofd"):
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for name in zf.namelist():
                    assert b"\r" not in zf.read(name), "%s::%s" % (rel_path, name)
        elif rel_path.endswith((".xml", ".json", ".md")):
            assert b"\r" not in content, rel_path


def test_outputs_contain_no_cr(dataset):
    """生成物文本一律 LF（EOL 门的前半：生成器侧）。"""
    _assert_text_lf(dataset["out"])


def test_frozen_data_matches_generator(tmp_path):
    """冻结入仓数据 == 生成器默认参数输出（回归锚；改生成器必须重冻结）。

    PDF 字节依赖 reportlab 版本：无 reportlab 的环境（CI）跳过，由本机
    与 M6 干净环境验证。
    """
    if not (DATA_DIR / "ground_truth" / "manifest.json").exists():
        pytest.skip("data/ 尚未冻结生成数据")
    if not _has_module("reportlab"):
        pytest.skip("reportlab 未安装：PDF 位级回归需本机验证")
    out = tmp_path / "frozen_check"
    generate(str(out), seed=42, n=60, anomaly_rate=0.35,
             formats=["xml", "pdf", "ofd"])
    assert _tree_bytes(out / "invoices") == _tree_bytes(DATA_DIR / "invoices")
    assert _tree_bytes(out / "ground_truth") == _tree_bytes(DATA_DIR / "ground_truth")


def test_frozen_data_has_no_cr():
    """EOL 门：冻结入仓文本产物出现 CR 即大声失败（CI 无依赖可跑）。"""
    if not (DATA_DIR / "invoices").exists():
        pytest.skip("data/invoices 尚未冻结生成数据")
    _assert_text_lf(DATA_DIR / "invoices")
    _assert_text_lf(DATA_DIR / "ground_truth")


# ---------------------------------------------------------------- 分配器


def test_allocate_events_defaults():
    counts, seq_members = allocate_events(60, 0.35)
    assert sum(counts.values()) >= 1
    assert seq_members == 5  # 余量 1 -> SEQ 簇 4 扩 5（60*0.35=21 文件）
    total_files = sum(EVENT_UNITS[code] * count for code, count in counts.items())
    assert total_files + (seq_members - 4) == 21


def test_allocate_events_small_and_degenerate():
    counts, seq_members = allocate_events(24, 0.35)
    assert counts["INJ-DUP-EXACT"] == 1 and counts["INJ-SEQ"] == 0
    assert seq_members == 4
    counts, _ = allocate_events(2, 0.9)
    assert counts["INJ-DUP-EXACT"] == 1
    counts, _ = allocate_events(5, 0.35)
    assert counts["INJ-DUP-EXACT"] == 1


# ---------------------------------------------------------------- 真值结构


def test_truth_keys_consistent(dataset):
    out = dataset["out"]
    cards, expectations, manifest = (
        dataset["cards"], dataset["expectations"], dataset["manifest"])
    manifest_paths = {record["path"] for record in manifest["files"]}
    assert set(cards) == manifest_paths
    for record in manifest["files"]:
        assert (out / record["path"]).exists(), record["path"]
    files_by_number = {}
    for record in manifest["files"]:
        files_by_number.setdefault(record["invoice_number"], []).append(record["path"])
    for number, paths in files_by_number.items():
        assert expectations[number]["files"] == sorted(paths)
    assert set(expectations) == set(files_by_number)


def test_expectations_match_injection_table(dataset):
    """每个号码的 expect/also_expect 与注入码映射表完全一致（§1.3 对拍）。"""
    levels = {"error", "suspicious", "review"}
    for number, entry in dataset["expectations"].items():
        assert entry["injection"] in INJECTION_EXPECTATIONS, number
        expect, also_expect = INJECTION_EXPECTATIONS[entry["injection"]]
        assert entry["expect"] == expect, number
        assert entry["also_expect"] == also_expect, number
        for level in list(entry["expect"].values()) + list(entry["also_expect"].values()):
            assert level in levels, number


def test_injection_coverage(dataset):
    """默认参数下 9 类注入全部落地且含基线（M1 DoD：10 类清单）。"""
    injections = {entry["injection"] for entry in dataset["expectations"].values()}
    assert injections == set(INJECTION_EXPECTATIONS)
    assert dataset["summary"]["baseline"] > 0


def test_field_miss_registers_missing_fields(dataset):
    missed = [entry for entry in dataset["expectations"].values()
              if entry["injection"] == "INJ-FIELD-MISS"]
    assert missed, "FIELD-MISS 事件应存在"
    for entry in missed:
        assert entry["missing_fields"], entry


def test_cards_roundtrip(dataset):
    """真值卡 dict 与 InvoiceCard 往返一致（M4 字段基准的输入形态）。"""
    for path, payload in dataset["cards"].items():
        assert InvoiceCard.from_dict(payload).to_dict() == payload, path


# ---------------------------------------------------------------- 注入不变量


def test_copy_events_share_number_across_batches(dataset):
    files_by_number = {}
    for record in dataset["manifest"]["files"]:
        files_by_number.setdefault(record["invoice_number"], []).append(record)
    copies = {n: records for n, records in files_by_number.items() if len(records) == 2}
    assert copies, "应存在同号副本事件"
    for number, records in copies.items():
        injections = {r["injection"] for r in records}
        assert injections <= {"INJ-DUP-EXACT", "INJ-DUP-JOINT"}, number
        assert records[0]["batch_id"] != records[1]["batch_id"], number
    assert len(copies) == 2  # 默认参数：EXACT×1 + JOINT×1


def test_arithmetic_and_cn_consistency(dataset):
    from invoice_ledger_checker.generator.synthetic import MISSING_ITEM_TAX_RATE
    for path, payload in dataset["cards"].items():
        injection = dataset["expectations"][payload["invoice_number"]]["injection"]
        amount = Decimal(payload["amount"])
        tax = Decimal(payload["tax_amount"])
        total = Decimal(payload["total_with_tax"])
        items_amount = sum(Decimal(i["amount"]) for i in payload["items"])
        items_tax = sum(Decimal(i["tax_amount"]) for i in payload["items"])
        assert items_amount == amount and items_tax == tax, path
        if injection == "INJ-ARITH-SUM":
            assert amount + tax != total, path
        else:
            assert amount + tax == total, path
        if injection == "INJ-ARITH-CN":
            assert payload["total_with_tax_cn"] != encode_amount(payload["total_with_tax"])
        else:
            assert payload["total_with_tax_cn"] == encode_amount(payload["total_with_tax"])
        if injection == "INJ-FIELD-MISS":
            missing = dataset["expectations"][payload["invoice_number"]]["missing_fields"]
            if "remark" in missing:
                assert payload["remark"] == ""
            if "buyer_name" in missing:
                assert payload["buyer_name"] == ""
            if "buyer_tax_id" in missing:
                assert payload["buyer_tax_id"] == ""
            if MISSING_ITEM_TAX_RATE in missing:
                assert payload["items"][-1]["tax_rate"] == ""


def test_time_windows_against_batch_anchor(dataset):
    anchors = {b["batch_id"]: date.fromisoformat(b["expense_anchor"])
               for b in dataset["manifest"]["batches"]}
    files_by_number = {}
    for record in dataset["manifest"]["files"]:
        files_by_number.setdefault(record["invoice_number"], []).append(record)
    for record in dataset["manifest"]["files"]:
        entry = dataset["expectations"][record["invoice_number"]]
        if len(files_by_number[record["invoice_number"]]) == 2:
            continue  # 副本事件：日期继承原件，由副本专项测试覆盖
        card = dataset["cards"][record["path"]]
        issue = date.fromisoformat(card["issue_date"])
        delta = (anchors[record["batch_id"]] - issue).days
        if entry["injection"] == "INJ-TIME-FUTURE":
            assert delta < 0, record["path"]
        elif entry["injection"] == "INJ-TIME-STALE":
            assert delta >= 180, record["path"]
        else:
            assert 0 < delta <= 70, record["path"]


def test_seq_clusters(dataset):
    clusters = {}
    for number, entry in dataset["expectations"].items():
        if entry["injection"] == "INJ-SEQ":
            card = dataset["cards"][entry["files"][0]]
            clusters[number] = card
    assert clusters, "SEQ 事件应存在"
    # 按销售方归簇
    by_seller = {}
    for number, card in clusters.items():
        by_seller.setdefault(card["seller_tax_id"], []).append((number, card))
    for seller_tax, members in by_seller.items():
        assert len(members) >= 3, seller_tax
        suffixes = sorted(int(number[-8:]) for number, _ in members)
        assert suffixes == list(range(suffixes[0], suffixes[0] + len(suffixes)))
        dates = sorted(card["issue_date"] for _, card in members)
        span = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days
        assert span <= 7, seller_tax


def test_fuzzy_pairs(dataset):
    pairs = {}
    for number, entry in dataset["expectations"].items():
        if entry["injection"] == "INJ-DUP-FUZZY":
            pairs[number] = dataset["cards"][entry["files"][0]]
    assert pairs, "FUZZY 事件应存在"
    by_seller = {}
    for number, card in pairs.items():
        by_seller.setdefault(card["seller_tax_id"], []).append((number, card))
    for members in by_seller.values():
        assert len(members) == 2
        (n1, c1), (n2, c2) = members
        assert n1 != n2
        assert c1["total_with_tax"] == c2["total_with_tax"]
        delta = abs((date.fromisoformat(c1["issue_date"])
                     - date.fromisoformat(c2["issue_date"])).days)
        assert delta == 1


# ---------------------------------------------------------------- 格式产物


def test_xml_parses_and_carries_key_fields(dataset):
    xml_records = [record for record in dataset["manifest"]["files"]
                   if record["format"] == "xml"]
    assert xml_records, "XML 产物应存在"
    for record in xml_records:
        root = ET.fromstring((dataset["out"] / record["path"]).read_bytes())
        texts = {el.tag: (el.text or "") for el in root.iter()}
        card = dataset["cards"][record["path"]]
        assert texts["InvoiceNumber"] == card["invoice_number"]
        assert texts["TotalWithTax"] == card["total_with_tax"]
        assert texts["TotalWithTaxCN"] == card["total_with_tax_cn"]


def test_ofd_zip_structure(dataset):
    ofd_paths = [record["path"] for record in dataset["manifest"]["files"]
                 if record["format"] == "ofd"]
    assert ofd_paths, "OFD 产物应存在"
    for record in dataset["manifest"]["files"]:
        if record["format"] != "ofd":
            continue
        with zipfile.ZipFile(dataset["out"] / record["path"]) as zf:
            names = zf.namelist()
            assert "OFD.xml" in names and "Doc_0/Page_0/Content.xml" in names
            content = zf.read("Doc_0/Page_0/Content.xml").decode("utf-8")
            assert record["invoice_number"] in content


def test_pdf_text_layer_contains_number(dataset):
    if not _has_module("reportlab") or not _has_module("pdfplumber"):
        pytest.skip("reportlab/pdfplumber 未安装：PDF 文本层验证跳过")
    import pdfplumber

    pdf_paths = [record for record in dataset["manifest"]["files"]
                 if record["format"] == "pdf"]
    assert pdf_paths, "PDF 产物应存在"
    for record in pdf_paths[:3]:  # 抽验 3 张即可（同发射器，防全套重复开销）
        with pdfplumber.open(str(dataset["out"] / record["path"])) as pdf:
            text = pdf.pages[0].extract_text() or ""
        assert record["invoice_number"] in text, record["path"]
        card = dataset["cards"][record["path"]]
        assert card["total_with_tax"] in text, record["path"]
