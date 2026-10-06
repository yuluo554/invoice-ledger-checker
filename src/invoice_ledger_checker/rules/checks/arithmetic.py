"""算术复核两规则（plan/04 §3）：R-ARITH-01 价税合计复核 / R-ARITH-02 大写金额一致。

R-ARITH-01 子检查：Σ(明细金额)=amount、Σ(明细税额)=tax_amount、
amount+tax_amount=total_with_tax（容差内，默认 0.01）；明细字段缺失/空时
对应子检查跳过，不硬判。骨架种子（amount+tax=total）随 M3 扩为全量。

R-ARITH-02：total_with_tax 转中文大写 ≡ total_with_tax_cn（转换器
cn_amount.encode_amount 与生成器同源共用）；金额不可解析不硬判 → review。

金额字段非数值时不硬判 → review 级"待人工确认"（降级语义，防误报）。
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from ...cn_amount import encode_amount
from ...models import InvoiceCard
from ..engine import Finding

DEFAULT_TOLERANCE = "0.01"


def _finding(card: InvoiceCard, level: str, kind: str, detail: Dict[str, Any]) -> Finding:
    message = {
        "sum": "明细聚合不符：Σ明细金额/Σ明细税额 与合计金额/合计税额不一致",
        "total": "票面算术不符：金额 %s + 税额 %s ≠ 价税合计 %s"
                 % (card.amount, card.tax_amount, card.total_with_tax),
        "unparseable": "金额字段无法解析为数值，待人工确认（不硬判）",
    }[kind]
    evidence = {"check": kind}
    evidence.update(detail)
    return Finding(
        rule_id="R-ARITH-01",
        level=level,
        invoice_numbers=[card.invoice_number],
        message=message,
        evidence=evidence,
    )


def _to_decimal(text: str) -> Optional[Decimal]:
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError, ValueError):
        return None


def check_total_with_tax(card: InvoiceCard, ctx: Dict[str, Any]) -> List[Finding]:
    if not (card.amount and card.tax_amount and card.total_with_tax):
        return []  # 字段缺失由解析层 field_flags 负责，规则不越权
    tolerance = Decimal(str(ctx["params"].get("arith_tolerance", DEFAULT_TOLERANCE)))
    amount = _to_decimal(card.amount)
    tax = _to_decimal(card.tax_amount)
    total = _to_decimal(card.total_with_tax)
    if amount is None or tax is None or total is None:
        return [_finding(card, "review", "unparseable", {
            "amount": card.amount,
            "tax_amount": card.tax_amount,
            "total_with_tax": card.total_with_tax,
        })]

    findings: List[Finding] = []
    # 子检查 1：明细聚合（仅当每行明细的金额/税额均可数值化时才复核——
    # 部分行缺失时部分和必然偏小，硬判会误报）
    if card.items:
        item_amounts = [_to_decimal(item.amount) for item in card.items]
        item_taxes = [_to_decimal(item.tax_amount) for item in card.items]
        if all(v is not None for v in item_amounts + item_taxes):
            sum_amount = sum(item_amounts)
            sum_tax = sum(item_taxes)
            if abs(sum_amount - amount) > tolerance or abs(sum_tax - tax) > tolerance:
                findings.append(_finding(card, "error", "sum", {
                    "items_amount_sum": str(sum_amount),
                    "items_tax_sum": str(sum_tax),
                    "amount": card.amount,
                    "tax_amount": card.tax_amount,
                }))
    # 子检查 2：金额+税额=价税合计
    if abs((amount + tax) - total) > tolerance:
        findings.append(_finding(card, "error", "total", {
            "amount": card.amount,
            "tax_amount": card.tax_amount,
            "total_with_tax": card.total_with_tax,
            "expect_total": str(amount + tax),
        }))
    return findings


def check_total_cn_consistent(card: InvoiceCard, ctx: Dict[str, Any]) -> List[Finding]:
    if not (card.total_with_tax and card.total_with_tax_cn):
        return []  # 字段缺失由解析层 field_flags 负责，规则不越权
    try:
        expected_cn = encode_amount(card.total_with_tax)
    except ValueError:
        return [
            Finding(
                rule_id="R-ARITH-02",
                level="review",
                invoice_numbers=[card.invoice_number],
                message="价税合计不可解析，大写金额无法自动复核，待人工确认（不硬判）",
                evidence={"total_with_tax": card.total_with_tax,
                          "total_with_tax_cn": card.total_with_tax_cn},
            )
        ]
    if card.total_with_tax_cn.strip() != expected_cn:
        return [
            Finding(
                rule_id="R-ARITH-02",
                level="error",
                invoice_numbers=[card.invoice_number],
                message="大写金额与小写价税合计不符：大写 %s，按小写 %s 应为 %s"
                        % (card.total_with_tax_cn, card.total_with_tax, expected_cn),
                evidence={
                    "total_with_tax": card.total_with_tax,
                    "total_with_tax_cn": card.total_with_tax_cn,
                    "expect_cn": expected_cn,
                },
            )
        ]
    return []
