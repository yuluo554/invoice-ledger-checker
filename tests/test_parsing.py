"""解析层测试（M2）：冻结数据字段级对账 + 数值清洗 + 坏文件路径。

测试纪律（plan/03 §4）：核心 stdlib 直测（CI 无重依赖全绿）；PDF 相关用
pdfplumber（函数内导入），未安装时显式 skip——与 extras 惰性导入纪律一致。

对账口径（generator/synthetic.py 模块注释 §2）：真值卡 vs 解析卡字段级
展开对账，M2 自测门槛 F1>=0.95/文件（正式基准 M4 落 benchmarks）。
"""

import json
import os
from pathlib import Path

import pytest

from invoice_ledger_checker.models import InvoiceCard
from invoice_ledger_checker.parsing import ParserError
from invoice_ledger_checker.parsing.base import clean_numeric_text, is_decimal_text
from invoice_ledger_checker.parsing.ofd_parser import parse as ofd_parse
from invoice_ledger_checker.parsing.xml_parser import parse as xml_parse
from invoice_ledger_checker.benchmarks.field_match import compare

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
HAS_INVOICES = (DATA_DIR / "invoices").is_dir()


def _has_module(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None


requires_pdfplumber = pytest.mark.skipif(
    not _has_module("pdfplumber"), reason="pdfplumber 未安装（CI 无重依赖路径）")
requires_data = pytest.mark.skipif(
    not HAS_INVOICES, reason="data/invoices 冻结数据不在仓（generate 可重建）")


def _truth_cards():
    with open(DATA_DIR / "ground_truth" / "cards.json", encoding="utf-8") as fh:
        return json.load(fh)


def _manifest():
    with open(DATA_DIR / "ground_truth" / "manifest.json", encoding="utf-8") as fh:
        return json.load(fh)


def _abs(rel_path: str) -> str:
    return str(DATA_DIR / rel_path.replace("/", os.sep))


# ------------------------------------------------------------------ 冻结对账


@requires_data
def test_xml_frozen_full_reconciliation():
    """35 份冻结 XML vs cards.json 字段级对账：每份 F1>=0.95（DoD 门槛）。"""
    xml_cards = {p: c for p, c in _truth_cards().items() if p.endswith(".xml")}
    assert len(xml_cards) == 35
    for rel_path, truth in sorted(xml_cards.items()):
        card = xml_parse(_abs(rel_path))
        got = compare(truth, card.to_dict())
        assert got["f1"] >= 0.95, "%s F1=%.3f %s" % (
            rel_path, got["f1"], got["mismatches"][:4])


@requires_data
@requires_pdfplumber
def test_pdf_frozen_full_reconciliation():
    """22 份冻结 PDF vs cards.json 字段级对账：每份 F1>=0.95（DoD 门槛）。"""
    pdf_cards = {p: c for p, c in _truth_cards().items() if p.endswith(".pdf")}
    assert len(pdf_cards) == 22
    from invoice_ledger_checker.parsing.pdf_parser import parse as pdf_parse

    for rel_path, truth in sorted(pdf_cards.items()):
        card = pdf_parse(_abs(rel_path))
        got = compare(truth, card.to_dict())
        assert got["f1"] >= 0.95, "%s F1=%.3f %s" % (
            rel_path, got["f1"], got["mismatches"][:4])


@requires_data
def test_same_number_double_files_parse_without_error():
    """同号双文件（INJ-DUP-EXACT/JOINT 跨批次副本）逐份解析均不得报错。

    判重语义属台账主键与规则层（R-DUP-01/02），解析层只管一文件一卡。
    """
    by_number = {}
    for record in _manifest()["files"]:
        by_number.setdefault(record["invoice_number"], []).append(record)
    doubles = {n: recs for n, recs in by_number.items() if len(recs) == 2}
    assert len(doubles) >= 2, "冻结数据应含 EXACT/JOINT 两类同号副本"
    for number, records in sorted(doubles.items()):
        cards = []
        for record in sorted(records, key=lambda r: r["path"]):
            path = _abs(record["path"])
            if path.endswith(".ofd"):
                # OFD 副本 = P2 顺延语义，显式登记而非崩溃
                with pytest.raises(NotImplementedError):
                    ofd_parse(path)
                continue
            card = xml_parse(path) if path.endswith(".xml") else _parse_pdf(path)
            assert isinstance(card, InvoiceCard)
            assert card.invoice_number == number
            cards.append(card)
        if records[0]["injection"] == "INJ-DUP-EXACT" and len(cards) == 2:
            got = compare(cards[0].to_dict(), cards[1].to_dict())
            assert got["f1"] == 1.0, "EXACT 副本解析卡应字段全等"


def _parse_pdf(path: str) -> InvoiceCard:
    if not _has_module("pdfplumber"):
        pytest.skip("pdfplumber 未安装")
    from invoice_ledger_checker.parsing.pdf_parser import parse as pdf_parse

    return pdf_parse(path)


# ------------------------------------------------------------------ 数值清洗


@pytest.mark.parametrize("raw,expected", [
    ("￥1,234.56", "1234.56"),
    ("１２３．４５", "123.45"),
    (" 12 30 ", "1230"),
    ("-5.50", "-5.50"),
    ("0.13", "0.13"),
    ("￥55840.85", "55840.85"),
    ("123.45元", "123.45"),
])
def test_clean_numeric_text_strips_and_normalizes(raw, expected):
    assert clean_numeric_text(raw) == expected
    assert is_decimal_text(expected)


@pytest.mark.parametrize("raw", ["abc", "", "1.2.3", "nan", "inf", "1２x3"])
def test_is_decimal_text_rejects_non_numeric(raw):
    assert not is_decimal_text(clean_numeric_text(raw))


def test_xml_invalid_numeric_dropped_with_flag(tmp_path):
    """非法数值丢弃（留空串+flag+降置信度），不猜值。"""
    path = tmp_path / "bad_amount.xml"
    path.write_bytes(
        "<ElectronicInvoice><InvoiceHeader>"
        "<InvoiceNumber>25910000000000000001</InvoiceNumber>"
        "<InvoiceType>数电普票</InvoiceType><IssueDate>2026-01-01</IssueDate>"
        "<Seller><Name>甲</Name><TaxId>91FAKE000000000001</TaxId></Seller>"
        "<AmountWithoutTax>abc</AmountWithoutTax>"
        "<TotalWithTax>12,３４５.６７</TotalWithTax>"
        "</InvoiceHeader></ElectronicInvoice>".encode("utf-8"))
    card = xml_parse(str(path))
    assert card.amount == ""
    assert "amount#invalid_number_dropped" in card.field_flags
    assert card.total_with_tax == "12345.67"
    assert card.confidence < 1.0


def test_xml_namespace_fallback_matches_localname(tmp_path):
    """带命名空间的文档按 localname 降级匹配：可解析但降置信度+flag。"""
    path = tmp_path / "ns.xml"
    path.write_bytes(
        '<ElectronicInvoice xmlns="urn:test" version="synthetic-v1">'
        "<InvoiceHeader>"
        "<InvoiceNumber>25910000000000000002</InvoiceNumber>"
        "<InvoiceType>数电专票</InvoiceType><IssueDate>2026-01-02</IssueDate>"
        "<Seller><Name>乙</Name><TaxId>91FAKE000000000002</TaxId></Seller>"
        "</InvoiceHeader></ElectronicInvoice>".encode("utf-8"))
    card = xml_parse(str(path))
    assert card.invoice_number == "25910000000000000002"
    assert card.confidence == pytest.approx(0.9)
    assert "xml#namespace_localname_fallback" in card.field_flags


def test_xml_evidence_records_node_path(tmp_path):
    path = tmp_path / "ev.xml"
    path.write_bytes(
        "<ElectronicInvoice><InvoiceHeader>"
        "<InvoiceNumber>25910000000000000003</InvoiceNumber>"
        "<InvoiceType>数电普票</InvoiceType><IssueDate>2026-01-03</IssueDate>"
        "<Seller><Name>丙</Name><TaxId>91FAKE000000000003</TaxId></Seller>"
        "</InvoiceHeader></ElectronicInvoice>".encode("utf-8"))
    card = xml_parse(str(path))
    locs = {ev.location for ev in card.evidence}
    assert "/ElectronicInvoice/InvoiceHeader/InvoiceNumber" in locs
    assert any(ev.quote == "25910000000000000003"
               and ev.location == "/ElectronicInvoice/InvoiceHeader/InvoiceNumber"
               for ev in card.evidence)


def test_xml_absent_optional_fields_flagged_not_invented(tmp_path):
    """可选字段节点缺席 -> 空串 + #absent flag（防幻觉：缺失 != 造值）。"""
    path = tmp_path / "miss.xml"
    path.write_bytes(
        "<ElectronicInvoice><InvoiceHeader>"
        "<InvoiceNumber>25910000000000000004</InvoiceNumber>"
        "<InvoiceType>数电普票</InvoiceType><IssueDate>2026-01-04</IssueDate>"
        "<Seller><Name>丁</Name><TaxId>91FAKE000000000004</TaxId></Seller>"
        "</InvoiceHeader></ElectronicInvoice>".encode("utf-8"))
    card = xml_parse(str(path))
    assert card.buyer_name == ""
    assert card.remark == ""
    assert "buyer_name#absent" in card.field_flags
    assert "remark#absent" in card.field_flags


# ------------------------------------------------------------------ 坏文件路径


def test_xml_empty_file_raises_parser_error(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_bytes(b"")
    with pytest.raises(ParserError):
        xml_parse(str(path))


def test_xml_garbage_bytes_raises_parser_error(tmp_path):
    path = tmp_path / "junk.xml"
    path.write_bytes(b"\x00\x01\x02not-xml-at-all\xff")
    with pytest.raises(ParserError):
        xml_parse(str(path))


def test_xml_without_invoice_number_rejected(tmp_path):
    """主键缺失=结构失败（无主键的卡不得创建，models.InvoiceCard 同纪律）。"""
    path = tmp_path / "nonumber.xml"
    path.write_bytes(
        "<ElectronicInvoice><InvoiceHeader>"
        "<InvoiceType>数电普票</InvoiceType><IssueDate>2026-01-01</IssueDate>"
        "</InvoiceHeader></ElectronicInvoice>".encode("utf-8"))
    with pytest.raises(ParserError) as excinfo:
        xml_parse(str(path))
    assert "invoice_number" in str(excinfo.value)


def test_xml_wrong_root_rejected(tmp_path):
    path = tmp_path / "other.xml"
    path.write_bytes(b"<orders><item>x</item></orders>")
    with pytest.raises(ParserError):
        xml_parse(str(path))


@requires_pdfplumber
def test_pdf_garbage_bytes_raises_parser_error(tmp_path):
    from invoice_ledger_checker.parsing.pdf_parser import parse as pdf_parse

    path = tmp_path / "junk.pdf"
    path.write_bytes(b"this is not a pdf at all")
    with pytest.raises(ParserError):
        pdf_parse(str(path))


@requires_pdfplumber
def test_pdf_without_invoice_labels_rejected(tmp_path):
    """有文本层但无发票版式要素 -> 结构失败（不猜值）。"""
    from invoice_ledger_checker.parsing.pdf_parser import parse as pdf_parse

    path = tmp_path / "nolabel.pdf"
    path.write_bytes(_minimal_pdf("hello world no invoice labels here"))
    with pytest.raises(ParserError) as excinfo:
        pdf_parse(str(path))
    assert "标题" in str(excinfo.value)


def _minimal_pdf(text: str) -> bytes:
    """手工构造可被 pdfminer 解析的极简单页 PDF（不依赖 reportlab）。"""
    stream = ("BT /F1 12 Tf 20 60 Td (%s) Tj ET" % text).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 120] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for idx, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % idx + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref_pos)
    return bytes(out)


# ------------------------------------------------------------------ OFD（P2 顺延）


@requires_data
def test_ofd_stub_status_unchanged(tmp_path):
    """OFD 为 P2 顺延项：parse 显式 NotImplementedError，交 CLI 报告登记。"""
    ofd_files = [r["path"] for r in _manifest()["files"] if r["format"] == "ofd"]
    assert len(ofd_files) == 3
    with pytest.raises(NotImplementedError):
        ofd_parse(_abs(ofd_files[0]))
