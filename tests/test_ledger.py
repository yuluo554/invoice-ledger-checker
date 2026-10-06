"""SQLite 台账契约测试（schema 权威出处 plan/04 §4）。"""

import pytest

from invoice_ledger_checker.models import InvoiceCard, LineItem
from invoice_ledger_checker.storage import Ledger


def make_card(number="25910000000000123456"):
    return InvoiceCard(
        invoice_number=number,
        invoice_type="数电普票",
        issue_date="2026-01-05",
        seller_name="云图商贸有限公司",
        seller_tax_id="91330100DEMOFAKE02",
        items=[LineItem(name="会议服务费", amount="1000.00", tax_rate="0.13", tax_amount="130.00")],
        amount="1000.00",
        tax_amount="130.00",
        total_with_tax="1130.00",
    )


def test_add_and_roundtrip(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    ledger.create_batch("b1", source_desc="测试", file_count=1)
    assert ledger.add_invoice(make_card(), "b1") is True
    assert ledger.count_invoices() == 1
    cards = list(ledger.iter_cards())
    assert cards[0].invoice_number == "25910000000000123456"
    assert cards[0].batch_id == "b1"
    assert cards[0].items[0].amount == "1000.00"
    ledger.close()


def test_duplicate_number_is_rejected_not_overwritten(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    ledger.create_batch("b1")
    assert ledger.add_invoice(make_card(), "b1") is True
    # 同号二次导入：R-DUP-01 信号，必须拒收而非覆盖
    assert ledger.add_invoice(make_card(), "b1") is False
    assert ledger.count_invoices() == 1
    ledger.close()


def test_create_batch_idempotent_on_rerun(tmp_path):
    """重跑 check 不崩：同批次重复登记保持首次记录（M3 幂等语义）。"""
    ledger = Ledger(str(tmp_path / "ledger.db"))
    assert ledger.create_batch("b1", source_desc="首次", file_count=3) == "b1"
    assert ledger.create_batch("b1", source_desc="重跑", file_count=5) == "b1"
    row = ledger.conn.execute(
        "SELECT source_desc, file_count FROM batches WHERE batch_id='b1'").fetchone()
    assert row == ("首次", 3)
    ledger.close()


def test_existing_numbers_for_persistent_dup_detection(tmp_path):
    """R-DUP-01 持久判重输入：入库前台账既有号码集（plan/04 §3.1）。"""
    ledger = Ledger(str(tmp_path / "ledger.db"))
    ledger.create_batch("b1")
    assert ledger.existing_numbers() == set()
    ledger.add_invoice(make_card(), "b1")
    ledger.add_invoice(make_card("25910000000000123457"), "b1")
    assert ledger.existing_numbers() == {
        "25910000000000123456", "25910000000000123457"}
    ledger.close()


def test_findings_roundtrip(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    finding = {
        "finding_id": "R-ARITH-01:25910000000000123457",
        "rule_id": "R-ARITH-01",
        "level": "error",
        "invoice_numbers": ["25910000000000123457"],
        "message": "票面算术不符",
        "evidence": {"amount": "2000.00"},
    }
    assert ledger.add_finding(finding, batch_id="b1") is True
    stored = ledger.list_findings()
    assert stored[0]["rule_id"] == "R-ARITH-01"
    assert stored[0]["level"] == "error"
    assert stored[0]["status"] == "open"
    assert stored[0]["evidence"] == {"amount": "2000.00"}
    # 同 finding_id 幂等拒收
    assert ledger.add_finding(finding) is False
    # 缺必填字段即拒绝
    with pytest.raises(ValueError):
        ledger.add_finding({"rule_id": "R-X", "level": "error"})
    ledger.close()


def test_level_check_constraint(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    with pytest.raises(Exception):  # SQLite CHECK 约束
        ledger.add_finding(
            {
                "finding_id": "x",
                "rule_id": "R-X",
                "level": "fatal",
                "invoice_numbers": [],
                "message": "非法级别",
            }
        )
    ledger.close()
