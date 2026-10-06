"""内置规则实现：M3 全量八规则（plan/04 §3 规则表 + §3.1 执行契约）。

注册顺序 = 执行顺序（R-DUP-03 门控依赖 R-DUP-01/02 已命中集，必须在前）。
"""

from typing import List

from ..engine import Rule
from .arithmetic import check_total_cn_consistent, check_total_with_tax
from .duplicate import (
    check_fuzzy_duplicate,
    check_in_batch_duplicate,
    check_joint_key_duplicate,
)
from .sequence import check_sequence_cluster
from .time_rules import check_issue_after_anchor, check_stale_period


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
            rule_id="R-DUP-02",
            name="联合键重复：同号同额同日期跨批次再制票",
            level="error",
            scope="batch",
            func=check_joint_key_duplicate,
        ),
        Rule(
            rule_id="R-DUP-03",
            name="模糊重复：同销售方邻近日期同额近似票",
            level="suspicious",
            scope="batch",
            func=check_fuzzy_duplicate,
        ),
        Rule(
            rule_id="R-SEQ-01",
            name="连号拆分簇：同销售方号码连续",
            level="suspicious",
            scope="batch",
            func=check_sequence_cluster,
        ),
        Rule(
            rule_id="R-ARITH-01",
            name="价税合计复核：明细聚合与金额+税额=价税合计",
            level="error",
            scope="card",
            func=check_total_with_tax,
        ),
        Rule(
            rule_id="R-ARITH-02",
            name="大写金额一致：大写与小写价税合计互核",
            level="error",
            scope="card",
            func=check_total_cn_consistent,
        ),
        Rule(
            rule_id="R-TIME-01",
            name="开票晚于导入：时间逻辑异常",
            level="error",
            scope="card",
            func=check_issue_after_anchor,
        ),
        Rule(
            rule_id="R-TIME-02",
            name="跨期异常：报销基准月前超 N 期",
            level="review",
            scope="card",
            func=check_stale_period,
        ),
    ]
