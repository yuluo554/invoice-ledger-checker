"""规则引擎与八规则测试（契约 plan/04 §3/§3.1；真值语义 generator/synthetic.py）。"""

import pytest

from invoice_ledger_checker.models import InvoiceCard, LineItem
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


def build_card(number="25910000000000123456", issue_date="2026-01-05",
               seller_tax_id="91330100FAKE000001", seller_name="云图商贸有限公司",
               amount="1000.00", tax="130.00", total="1130.00",
               cn="壹仟壹佰叁拾元整", batch_id="batch_01", items=None, **overrides):
    card = InvoiceCard(
        invoice_number=number,
        invoice_type="数电普票",
        issue_date=issue_date,
        buyer_name="星辰科技有限公司",
        buyer_tax_id="91330100FAKE000002",
        seller_name=seller_name,
        seller_tax_id=seller_tax_id,
        items=items if items is not None else [
            LineItem(name="会议服务费", amount=amount, tax_rate="0.13", tax_amount=tax),
        ],
        amount=amount,
        tax_amount=tax,
        total_with_tax=total,
        total_with_tax_cn=cn,
        batch_id=batch_id,
    )
    for key, value in overrides.items():
        setattr(card, key, value)
    return card


def seeded_engine(**params):
    engine = DetectionEngine(params=params)
    register_builtin(engine)
    return engine


def by_rule(findings, rule_id):
    return [f for f in findings if f.rule_id == rule_id]


# ---------------------------------------------------------------- 引擎契约


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


def test_builtin_registers_eight_rules_in_contract_order():
    engine = seeded_engine()
    assert engine.rule_ids == [
        "R-DUP-01", "R-DUP-02", "R-DUP-03", "R-SEQ-01",
        "R-ARITH-01", "R-ARITH-02", "R-TIME-01", "R-TIME-02",
    ]


def test_finding_id_joins_all_numbers():
    """三张同销售方同额邻近日卡 -> DUP-03 三对；finding_id 收全部号码且互异。"""
    findings = seeded_engine().run([
        build_card(),
        build_card(number="25910000000000123457", issue_date="2026-01-06"),
        build_card(number="25910000000000123458", issue_date="2026-01-06"),
    ])
    fuzzy = by_rule(findings, "R-DUP-03")
    assert len(fuzzy) == 3
    ids = {f.finding_id for f in fuzzy}
    assert ids == {
        "R-DUP-03:25910000000000123456|25910000000000123457",
        "R-DUP-03:25910000000000123456|25910000000000123458",
        "R-DUP-03:25910000000000123457|25910000000000123458",
    }


# ---------------------------------------------------------------- R-ARITH-01


def test_arith_ok_card_produces_no_finding():
    findings = seeded_engine().run([build_card()])
    assert findings == []


def test_arith_tampered_total_is_error():
    card = build_card(total="2180.00", cn="贰仟壹佰捌拾元整")  # 应为 1130.00
    findings = seeded_engine().run([card])
    assert len(findings) == 1
    assert findings[0].rule_id == "R-ARITH-01"
    assert findings[0].level == "error"
    assert findings[0].finding_id.startswith("R-ARITH-01:")
    assert findings[0].evidence["expect_total"] == "1130.00"


def test_arith_non_numeric_degrades_to_review():
    card = build_card(amount="一千元")  # 非数值：不硬判
    findings = seeded_engine().run([card])
    assert findings[0].level == "review"


def test_arith_tolerance_param_respected():
    # 0.005 差异在默认容差 0.01 内 -> 无 finding；容差收紧为 0.001 -> error
    # 大写与四舍五入后小写一致（1130.005 -> 1130.01），隔离出纯容差场景
    card = build_card(total="1130.005", cn="壹仟壹佰叁拾元零壹分")
    assert seeded_engine().run([card]) == []
    strict = seeded_engine(arith_tolerance="0.001")
    assert strict.run([card])[0].level == "error"


def test_arith_item_sum_mismatch_is_error():
    # 明细行金额之和 != 合计金额（明细税额一致）
    card = build_card(
        items=[
            LineItem(name="咨询费", amount="800.00", tax_rate="0.13", tax_amount="130.00"),
            LineItem(name="服务费", amount="100.00", tax_rate="0.13", tax_amount="0.00"),
        ],
    )
    findings = seeded_engine().run([card])
    assert len(findings) == 1
    assert findings[0].evidence["check"] == "sum"


def test_arith_item_check_skipped_when_item_values_incomplete():
    # 明细行金额缺失 -> 聚合子检查跳过（不硬判），合计子检查仍通过
    card = build_card(
        items=[LineItem(name="咨询费", amount="", tax_rate="0.13", tax_amount="130.00")],
    )
    assert seeded_engine().run([card]) == []


def test_arith_item_and_total_subchecks_can_both_fire():
    card = build_card(
        amount="2000.00", tax="260.00", total="9999.00", cn="玖仟玖佰玖拾玖元整",
        items=[LineItem(name="咨询费", amount="100.00", tax_rate="0.13",
                        tax_amount="260.00")],
    )
    checks = {f.evidence["check"] for f in seeded_engine().run([card])}
    assert checks == {"sum", "total"}


# ---------------------------------------------------------------- R-ARITH-02


def test_cn_mismatch_is_error():
    card = build_card(cn="壹仟贰佰元整")  # 应为 壹仟壹佰叁拾元整
    findings = by_rule(seeded_engine().run([card]), "R-ARITH-02")
    assert len(findings) == 1
    assert findings[0].level == "error"
    assert findings[0].evidence["expect_cn"] == "壹仟壹佰叁拾元整"


def test_cn_ok_passes():
    assert by_rule(seeded_engine().run([build_card()]), "R-ARITH-02") == []


def test_cn_unparseable_total_degrades_to_review():
    card = build_card(total="１１３０元", cn="壹仟壹佰叁拾元整")  # 全角混排不可解析
    findings = by_rule(seeded_engine().run([card]), "R-ARITH-02")
    assert findings[0].level == "review"


def test_cn_missing_fields_skipped():
    card = build_card(total="", cn="")
    assert by_rule(seeded_engine().run([card]), "R-ARITH-02") == []


# ---------------------------------------------------------------- R-DUP-01


def test_duplicate_number_in_batch_is_error():
    cards = [build_card(), build_card(), build_card("25910000000000123457")]
    findings = seeded_engine().run(cards)
    dup = by_rule(findings, "R-DUP-01")
    assert len(dup) == 1
    assert dup[0].invoice_numbers == ["25910000000000123456"]
    assert dup[0].level == "error"
    assert dup[0].evidence["occurrences"] == 2


def test_duplicate_pre_existing_in_ledger_is_error():
    card = build_card()
    findings = seeded_engine().run([card], {"existing_numbers": {card.invoice_number}})
    dup = by_rule(findings, "R-DUP-01")
    assert len(dup) == 1
    assert dup[0].evidence["pre_existing_in_ledger"] is True


def test_missing_amount_fields_are_skipped_not_flagged():
    card = build_card(amount="", tax="", total="")
    assert seeded_engine().run([card]) == []


# ---------------------------------------------------------------- R-DUP-02


def test_joint_key_reissued_pair_is_error():
    original = build_card()
    twin = build_card(batch_id="batch_02", buyer_name="另一家收购主体有限公司",
                      remark="再制票备注")
    findings = seeded_engine().run([original, twin])
    joint = by_rule(findings, "R-DUP-02")
    assert len(joint) == 1
    assert joint[0].level == "error"
    assert joint[0].evidence["pairs"][0]["batches"] == ["batch_01", "batch_02"]


def test_exact_copy_excluded_from_joint_key_rule():
    original = build_card()
    copy_card = build_card(batch_id="batch_02")  # 字段全等纯复制件
    findings = seeded_engine().run([original, copy_card])
    assert by_rule(findings, "R-DUP-02") == []
    assert len(by_rule(findings, "R-DUP-01")) == 1


def test_joint_key_same_batch_not_flagged():
    original = build_card()
    twin = build_card(batch_id="batch_01", buyer_name="另一家收购主体有限公司")
    assert by_rule(seeded_engine().run([original, twin]), "R-DUP-02") == []


def test_joint_key_different_total_or_date_not_flagged():
    original = build_card()
    other_total = build_card(number=original.invoice_number, batch_id="batch_02",
                             total="2260.00", cn="贰仟贰佰陆拾元整",
                             amount="2000.00", tax="260.00")
    other_date = build_card(number=original.invoice_number, batch_id="batch_02",
                            issue_date="2026-01-06")
    engine = seeded_engine()
    assert by_rule(engine.run([original, other_total]), "R-DUP-02") == []
    assert by_rule(engine.run([original, other_date]), "R-DUP-02") == []


# ---------------------------------------------------------------- R-DUP-03


def test_fuzzy_pair_flagged_for_both_numbers():
    first = build_card()
    near = build_card(number="25910000000000123457", issue_date="2026-01-06")
    findings = by_rule(seeded_engine().run([first, near]), "R-DUP-03")
    assert len(findings) == 1
    assert findings[0].level == "suspicious"
    assert findings[0].invoice_numbers == [
        "25910000000000123456", "25910000000000123457"]
    assert findings[0].evidence["amount"] == "1130.00"


def test_fuzzy_gated_by_dup01_hits():
    """门控互斥：已被 R-DUP-01 命中的号码不参与 R-DUP-03 配对（plan/04 §3）。"""
    original = build_card()
    copy_card = build_card(batch_id="batch_02")          # 同号副本 -> DUP-01
    other = build_card(number="25910000000000123457",
                       issue_date="2026-01-05")          # 与副本同销售方同日同额
    findings = seeded_engine().run([original, copy_card, other])
    assert len(by_rule(findings, "R-DUP-01")) == 1
    assert by_rule(findings, "R-DUP-03") == []


def test_fuzzy_amount_or_seller_mismatch_not_flagged():
    first = build_card()
    other_amount = build_card(number="25910000000000123457", issue_date="2026-01-06",
                              total="1131.00", cn="壹仟壹佰叁拾壹元整",
                              amount="1001.00", tax="130.00")
    other_seller = build_card(number="25910000000000123458", issue_date="2026-01-05",
                              seller_tax_id="91330100FAKE000009",
                              seller_name="别家公司有限公司")
    engine = seeded_engine()
    assert by_rule(engine.run([first, other_amount]), "R-DUP-03") == []
    assert by_rule(engine.run([first, other_seller]), "R-DUP-03") == []


def test_fuzzy_date_window_param_respected():
    first = build_card()
    near = build_card(number="25910000000000123457", issue_date="2026-01-08")  # 差 3 天
    assert by_rule(seeded_engine().run([first, near]), "R-DUP-03") == []
    loose = seeded_engine(dup_date_window_days=5)
    assert len(by_rule(loose.run([first, near]), "R-DUP-03")) == 1


# ---------------------------------------------------------------- R-SEQ-01


def seq_cards(suffix_start, count, seller_tax_id="91330100FAKE000001",
              prefix="259100000000", start_day=1, batch_id="batch_01"):
    return [
        build_card(
            number="%s%08d" % (prefix, suffix_start + i),
            issue_date="2026-01-%02d" % (start_day + i),
            seller_tax_id=seller_tax_id,
            batch_id=batch_id,
        )
        for i in range(count)
    ]


def test_sequence_cluster_flagged():
    cards = seq_cards(10000101, 3)
    findings = by_rule(seeded_engine().run(cards), "R-SEQ-01")
    assert len(findings) == 1
    assert findings[0].level == "suspicious"
    assert len(findings[0].invoice_numbers) == 3
    assert findings[0].evidence["count"] == 3


def test_sequence_below_min_len_not_flagged():
    assert by_rule(seeded_engine().run(seq_cards(10000101, 2)), "R-SEQ-01") == []


def test_sequence_suffix_gap_breaks_cluster():
    cards = seq_cards(10000101, 2) + seq_cards(10000104, 2)
    assert by_rule(seeded_engine().run(cards), "R-SEQ-01") == []


def test_sequence_date_span_beyond_window_not_flagged():
    cards = [
        build_card(number="259100000000100001%02d" % (i + 1),
                   issue_date="2026-01-%02d" % (1 + i * 5),  # 跨度 10 天 > 7
                   seller_tax_id="91330100FAKE000001")
        for i in range(3)
    ]
    assert by_rule(seeded_engine().run(cards), "R-SEQ-01") == []


def test_sequence_mixed_prefix_not_flagged():
    """前缀不同只警示不判异常（M3 定稿：跨前缀不产出 finding）。"""
    cards = seq_cards(10000101, 3) + seq_cards(10000104, 1, prefix="269100000000")
    assert by_rule(seeded_engine().run(cards), "R-SEQ-01") == []


def test_sequence_requires_same_seller():
    cards = [
        build_card(number="259100000000100001%02d" % (i + 1),
                   issue_date="2026-01-0%d" % (i + 1),
                   seller_tax_id="91330100FAKE00000%d" % (i + 1))
        for i in range(3)
    ]
    assert by_rule(seeded_engine().run(cards), "R-SEQ-01") == []


# ---------------------------------------------------------------- R-TIME


def time_ctx(anchor="2026-07-15"):
    return {
        "batch_anchors": {"batch_01": anchor},
        "default_anchor": "2026-12-31",
    }


def test_time_future_issue_is_error():
    card = build_card(issue_date="2026-07-16")  # 晚于 anchor 一天
    findings = by_rule(seeded_engine().run([card], time_ctx()), "R-TIME-01")
    assert len(findings) == 1
    assert findings[0].level == "error"
    assert findings[0].evidence["delta_days"] == 1


def test_time_issue_on_or_before_anchor_passes():
    on_day = build_card(issue_date="2026-07-15")
    before = build_card(issue_date="2026-05-01")
    assert by_rule(seeded_engine().run([on_day, before], time_ctx()), "R-TIME-01") == []


def test_time_default_anchor_used_when_batch_unmapped():
    card = build_card(issue_date="2027-01-01", batch_id="batch_99")
    findings = by_rule(seeded_engine().run(
        [card], {"default_anchor": "2026-07-15"}), "R-TIME-01")
    assert len(findings) == 1
    assert findings[0].evidence["anchor"] == "2026-07-15"


def test_time_no_anchor_at_all_skips():
    card = build_card(issue_date="2027-01-01")
    assert by_rule(seeded_engine().run([card]), "R-TIME-01") == []


def test_time_stale_beyond_n_period_is_review():
    card = build_card(issue_date="2026-01-01")  # 距 2026-07 跨 6 期
    findings = by_rule(seeded_engine().run([card], time_ctx()), "R-TIME-02")
    assert len(findings) == 1
    assert findings[0].level == "review"
    assert findings[0].evidence["months_behind"] == 6


def test_time_within_n_period_passes():
    recent = build_card(issue_date="2026-05-01")   # 跨 2 期
    assert by_rule(seeded_engine().run([recent], time_ctx()), "R-TIME-02") == []


def test_time_future_not_double_flagged_by_stale():
    """R-TIME-02 方向定稿：仅追溯方向——未来票只报 R-TIME-01，不双报。"""
    card = build_card(issue_date="2027-06-01")  # 未来 11 个月
    findings = seeded_engine().run([card], time_ctx())
    assert [f.rule_id for f in findings] == ["R-TIME-01"]


def test_time_n_period_param_respected():
    card = build_card(issue_date="2026-05-01")  # 跨 2 期
    strict = seeded_engine(time_n_period=1)
    findings = by_rule(strict.run([card], time_ctx()), "R-TIME-02")
    assert len(findings) == 1


def test_time_unparseable_date_skipped():
    card = build_card(issue_date="二〇二六年七月一日")
    assert seeded_engine().run([card], time_ctx()) == []
