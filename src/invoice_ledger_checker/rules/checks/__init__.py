"""内置规则实现。骨架期：R-DUP-01 + R-ARITH-01 种子；M3 全量八规则（plan/04 §3）。"""

from typing import List

from .arithmetic import check_total_with_tax
from .duplicate import check_in_batch_duplicate
from ..engine import Rule


def builtin_rules() -> List[Rule]:
    return [
        Rule(
            rule_id="R-DUP-01",
            name="精确重复：同一发票号码重复导入",
            level="error",
            scope="batch",
            func=check_in_batch_duplicate,
        ),
        Rule(
            rule_id="R-ARITH-01",
            name="价税合计复核：金额+税额=价税合计",
            level="error",
            scope="card",
            func=check_total_with_tax,
        ),
    ]
