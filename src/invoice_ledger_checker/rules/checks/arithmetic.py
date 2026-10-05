"""R-ARITH-01 价税合计复核（种子版随骨架交付，plan/04 §3）。

骨架实现子检查：amount + tax_amount = total_with_tax（容差内）。
明细级聚合复核（Σ明细=合计、明细税额=合计税额）随 M3 加入。
金额字段非数值时不硬判 → review 级"待人工确认"（降级语义，防误报）。
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from ...models import InvoiceCard
from ..engine import Finding

DEFAULT_TOLERANCE = "0.01"


def check_total_with_tax(card: InvoiceCard, ctx: Dict[str, Any]) -> List[Finding]:
    if not (card.amount and card.tax_amount and card.total_with_tax):
        return []  # 字段缺失由解析层 field_flags 负责，规则不越权
    tolerance = Decimal(ctx["params"].get("arith_tolerance", DEFAULT_TOLERANCE))
    try:
        amount = Decimal(card.amount)
        tax = Decimal(card.tax_amount)
        total = Decimal(card.total_with_tax)
    except InvalidOperation:
        return [
            Finding(
                rule_id="R-ARITH-01",
                level="review",
                invoice_numbers=[card.invoice_number],
                message="金额字段无法解析为数值，待人工确认（不硬判）",
                evidence={
                    "amount": card.amount,
                    "tax_amount": card.tax_amount,
                    "total_with_tax": card.total_with_tax,
                },
            )
        ]
    if abs((amount + tax) - total) > tolerance:
        return [
            Finding(
                rule_id="R-ARITH-01",
                level="error",
                invoice_numbers=[card.invoice_number],
                message="票面算术不符：金额 %s + 税额 %s ≠ 价税合计 %s"
                % (card.amount, card.tax_amount, card.total_with_tax),
                evidence={
                    "amount": card.amount,
                    "tax_amount": card.tax_amount,
                    "total_with_tax": card.total_with_tax,
                    "expect_total": str(amount + tax),
                },
            )
        ]
    return []
