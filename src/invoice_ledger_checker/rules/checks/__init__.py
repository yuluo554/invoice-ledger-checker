"""内置规则实现：M3 全量八规则（plan/04 §3 规则表 + §3.1 执行契约）。

注册顺序 = 执行顺序（R-DUP-03 门控依赖 R-DUP-01/02 已命中集，必须在前）。

法规依据（M7 追加，不参与判定）：每条 Rule 的 basis 挂「法规 + 条号 + 逐字引文 +
知识库引用」。引文为字面字符串（运行期**不读** data/knowledge——知识库不在
wheel 里），与 data/knowledge/*.json 的 entries[*].quote 逐字一致由
tests/test_knowledge.py 断言（单一事实源，不引入运行期依赖）。
"""

from typing import Any, Dict, List

from ..engine import Rule
from .arithmetic import check_total_cn_consistent, check_total_with_tax
from .duplicate import (
    check_fuzzy_duplicate,
    check_in_batch_duplicate,
    check_joint_key_duplicate,
)
from .sequence import check_sequence_cluster
from .time_rules import check_issue_after_anchor, check_stale_period

# ---- 被引用的条文（quote 从 data/knowledge/*.json 原样复制，一字不改）----

_REG_764 = "中华人民共和国国务院令第764号：《国务院关于修改和废止部分行政法规的决定》（对《中华人民共和国发票管理办法》的修改）"
_REG_764_SHORT = "发票管理办法（2023 修订）"
_REG_11 = "国家税务总局公告2024年第11号：《国家税务总局关于推广应用全面数字化电子发票的公告》"
_REG_11_SHORT = "11 号公告（数电票推广应用）"

_Q_764_21_1 = (
    "开具发票应当按照规定的时限、顺序、栏目，全部联次一次性如实开具，"
    "开具纸质发票应当加盖发票专用章。"
)
_Q_764_21_2 = (
    "任何单位和个人不得有下列虚开发票行为：（一）为他人、为自己开具与实际经营业务情况不符的发票；"
    "（二）让他人为自己开具与实际经营业务情况不符的发票；（三）介绍他人开具与实际经营业务情况不符的发票。"
)
_Q_NO11_DEFINITION = (
    "数电发票是《中华人民共和国发票管理办法》中“电子发票”的一种，"
    "是将发票的票面要素全面数字化、号码全国统一赋予、开票额度智能授予、"
    "信息通过税务数字账户等方式在征纳主体之间自动流转的新型发票。"
    "数电发票与纸质发票具有同等法律效力。"
)
_Q_NO11_NUMBER_RULE = (
    "数电发票的号码为20位，其中：第1-2位代表公历年度的后两位，"
    "第3-4位代表开票方所在的省级税务局区域代码，第5位代表开具渠道等信息，"
    "第6-20位为顺序编码。"
)

# 弱关联三规则如实披露口径（法规无直接禁止条款，条号仅挂同类义务上位条款）
_HEURISTIC_NOTE = (
    "工程口径：本规则为启发式风险信号，法规无直接禁止条款；条号仅挂同类义务的上位条款"
)


def _basis_764_21_1() -> Dict[str, Any]:
    return {
        "regulation": _REG_764,
        "regulation_short": _REG_764_SHORT,
        "article": "第二十一条第一款",
        "knowledge_ref": "764号令.json#764-21-1",
        "quote": _Q_764_21_1,
    }


def _basis_764_21_2() -> Dict[str, Any]:
    return {
        "regulation": _REG_764,
        "regulation_short": _REG_764_SHORT,
        "article": "第二十一条第二款",
        "knowledge_ref": "764号令.json#764-21-2",
        "quote": _Q_764_21_2,
    }


def _basis_no11_definition() -> Dict[str, Any]:
    return {
        "regulation": _REG_11,
        "regulation_short": _REG_11_SHORT,
        "article": "第一条",
        "knowledge_ref": "11号公告.json#no11-definition",
        "quote": _Q_NO11_DEFINITION,
    }


def _basis_no11_number_rule() -> Dict[str, Any]:
    return {
        "regulation": _REG_11,
        "regulation_short": _REG_11_SHORT,
        "article": "第四条",
        "knowledge_ref": "11号公告.json#no11-number-rule",
        "quote": _Q_NO11_NUMBER_RULE,
    }


def _with_note(basis: Dict[str, Any], note: str = _HEURISTIC_NOTE) -> Dict[str, Any]:
    payload = dict(basis)
    payload["note"] = note
    return payload


def builtin_rules() -> List[Rule]:
    return [
        Rule(
            rule_id="R-DUP-01",
            name="精确重复：同一发票号码重复导入",
            level="error",
            scope="batch",
            func=check_in_batch_duplicate,
            basis=_basis_no11_definition(),
        ),
        Rule(
            rule_id="R-DUP-02",
            name="联合键重复：同号同额同日期跨批次再制票",
            level="error",
            scope="batch",
            func=check_joint_key_duplicate,
            basis=_basis_764_21_2(),
        ),
        Rule(
            rule_id="R-DUP-03",
            name="模糊重复：同销售方邻近日期同额近似票",
            level="suspicious",
            scope="batch",
            func=check_fuzzy_duplicate,
            basis=_basis_764_21_2(),
        ),
        Rule(
            rule_id="R-SEQ-01",
            name="连号拆分簇：同销售方号码连续",
            level="suspicious",
            scope="batch",
            func=check_sequence_cluster,
            basis=_with_note(_basis_no11_number_rule()),
        ),
        Rule(
            rule_id="R-ARITH-01",
            name="价税合计复核：明细聚合与金额+税额=价税合计",
            level="error",
            scope="card",
            func=check_total_with_tax,
            basis=_basis_764_21_1(),
        ),
        Rule(
            rule_id="R-ARITH-02",
            name="大写金额一致：大写与小写价税合计互核",
            level="error",
            scope="card",
            func=check_total_cn_consistent,
            basis=_basis_764_21_1(),
        ),
        Rule(
            rule_id="R-TIME-01",
            name="开票晚于导入：时间逻辑异常",
            level="error",
            scope="card",
            func=check_issue_after_anchor,
            basis=_with_note(_basis_764_21_1()),
        ),
        Rule(
            rule_id="R-TIME-02",
            name="跨期异常：报销基准月前超 N 期",
            level="review",
            scope="card",
            func=check_stale_period,
            basis=_with_note(_basis_764_21_1()),
        ),
    ]
