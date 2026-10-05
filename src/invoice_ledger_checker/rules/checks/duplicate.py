"""R-DUP-01 精确重复（种子版）：同一发票号码在本次导入集合中出现多次。

骨架版只做批内判重（数据已在内存）；M3 接入台账持久判重
（invoices 主键冲突 → error Finding，plan/04 §3）。
"""

from typing import Any, Dict, List

from ...models import InvoiceCard
from ..engine import Finding


def check_in_batch_duplicate(cards: List[InvoiceCard], ctx: Dict[str, Any]) -> List[Finding]:
    counts: Dict[str, int] = {}
    for card in cards:
        counts[card.invoice_number] = counts.get(card.invoice_number, 0) + 1
    findings = []
    for number, count in counts.items():
        if count > 1:
            findings.append(
                Finding(
                    rule_id="R-DUP-01",
                    level="error",
                    invoice_numbers=[number],
                    message="发票号码在本次导入中重复出现 %d 次，疑似重复报销" % count,
                    evidence={"count": count},
                )
            )
    return findings
