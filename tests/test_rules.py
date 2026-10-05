"""规则引擎与种子规则测试（R-ARITH-01 / R-DUP-01；契约 plan/04 §3）。"""

import pytest

from invoice_ledger_checker.models import InvoiceCard
from invoice_ledger_checker.rules import DetectionEngine, Rule, register_builtin


def make_card(number="25910000000000123456", amount="1000.00", tax="130.00", total="1130.00"):
    return InvoiceCard(
        invoice_number=number,
        invoice_type="数电普票",
        issue_date="2026-01-05",
        amount=amount,
        tax_amount=tax,
        total_with_tax=total,
    )


def seeded_engine(**params):
    engine = DetectionEngine(params=params)
    register_builtin(engine)
    return engine


def test_register_rejects_duplicate_rule_id():
    engine = DetectionEngine()
    engine.register(Rule("R-X", "x", "error", "card", lambda c, ctx: []))
    with pytest.raises(ValueError):
        engine.register(Rule("R-X", "x2", "error", "card", lambda c, ctx: []))


def test_register_rejects_invalid_level_or_scope():
    with pytest.raises(ValueError):
        Rule("R-X", "x", "fatal", "card", lambda c, ctx: [])
    with pytest.raises(ValueError):
        Rule("R-X", "x", "error", "global", lambda c, ctx: [])


def test_arith_ok_card_produces_no_finding():
    findings = seeded_engine().run([make_card()])
    assert findings == []


def test_arith_tampered_total_is_error():
    card = make_card(total="2180.00")  # 应为 1130.00
    findings = seeded_engine().run([card])
    assert len(findings) == 1
    assert findings[0].rule_id == "R-ARITH-01"
    assert findings[0].level == "error"
    assert findings[0].finding_id.startswith("R-ARITH-01:")
    assert findings[0].evidence["expect_total"] == "1130.00"


def test_arith_non_numeric_degrades_to_review():
    card = make_card(amount="一千元")  # 非数值：不硬判
    findings = seeded_engine().run([card])
    assert findings[0].level == "review"


def test_arith_tolerance_param_respected():
    # 0.005 差异在默认容差 0.01 内 -> 无 finding；容差收紧为 0.001 -> error
    card = make_card(total="1130.005")
    assert seeded_engine().run([card]) == []
    strict = seeded_engine(arith_tolerance="0.001")
    assert strict.run([card])[0].level == "error"


def test_duplicate_number_in_batch_is_error():
    cards = [make_card(), make_card(), make_card("25910000000000123457")]
    findings = seeded_engine().run(cards)
    dup = [f for f in findings if f.rule_id == "R-DUP-01"]
    assert len(dup) == 1
    assert dup[0].invoice_numbers == ["25910000000000123456"]
    assert dup[0].level == "error"


def test_missing_amount_fields_are_skipped_not_flagged():
    card = make_card(amount="", tax="", total="")
    assert seeded_engine().run([card]) == []
