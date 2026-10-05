"""InvoiceCard 序列化契约测试（plan/04 §1：to_dict/from_dict 往返一致）。"""

import pytest

from invoice_ledger_checker.models import Evidence, InvoiceCard, LineItem


def make_card(**overrides):
    base = dict(
        invoice_number="25910000000000123456",
        invoice_type="数电普票",
        issue_date="2026-01-05",
        buyer_name="星辰科技有限公司",
        buyer_tax_id="91330100DEMOFAKE01",
        seller_name="云图商贸有限公司",
        seller_tax_id="91330100DEMOFAKE02",
        items=[LineItem(name="会议服务费", amount="1000.00", tax_rate="0.13", tax_amount="130.00")],
        amount="1000.00",
        tax_amount="130.00",
        total_with_tax="1130.00",
        total_with_tax_cn="壹仟壹佰叁拾元整",
        remark="",
        batch_id="batch-demo-001",
        confidence=1.0,
        field_flags=[],
        evidence=[Evidence(source_file="demo/a.xml", quote="1130.00", location="/Invoice/TotalAmount")],
    )
    base.update(overrides)
    return InvoiceCard(**base)


def test_dict_roundtrip_preserves_everything():
    card = make_card()
    restored = InvoiceCard.from_dict(card.to_dict())
    assert restored == card


def test_from_dict_rejects_missing_primary_key():
    with pytest.raises(ValueError):
        InvoiceCard.from_dict({"invoice_type": "数电普票"})


def test_from_dict_ignores_unknown_keys():
    data = make_card().to_dict()
    data["future_field"] = "anything"  # 向前兼容：未知键忽略
    restored = InvoiceCard.from_dict(data)
    assert restored.invoice_number == "25910000000000123456"


def test_default_card_is_full_confidence_no_flags():
    card = make_card()
    assert card.confidence == 1.0
    assert card.field_flags == []
