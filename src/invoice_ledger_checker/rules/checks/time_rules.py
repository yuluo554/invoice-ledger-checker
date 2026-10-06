"""时间逻辑两规则（plan/04 §3）：R-TIME-01 开票晚于导入 / R-TIME-02 跨期异常。

时间基准双通路（M3 定稿，plan/04 §3.1）：
- 基准通路：ctx["batch_anchors"] 提供批次 -> expense_anchor（manifest 固化，
  与墙钟无关——seed 可复现前提）；ctx["default_anchor"] 兜底无映射批次；
- 常规通路：check 命令不传 manifest 时 default_anchor=导入时刻（当天）。

R-TIME-02 方向定稿（对拍真值口径）：仅追溯方向——issue 早于 anchor 所在
月份超过 N 期才报 review；未来票由 R-TIME-01 全覆盖，双向判定会对
INJ-TIME-FUTURE 双报（误报）。
"""

from datetime import date
from typing import Any, Dict, List, Optional

from ...models import InvoiceCard
from ..engine import Finding

DEFAULT_N_PERIOD = 3


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _anchor_of(card: InvoiceCard, ctx: Dict[str, Any]) -> Optional[date]:
    anchors = ctx.get("batch_anchors") or {}
    anchor = anchors.get(card.batch_id, ctx.get("default_anchor"))
    return _as_date(anchor) if anchor is not None else None


def check_issue_after_anchor(card: InvoiceCard, ctx: Dict[str, Any]) -> List[Finding]:
    """R-TIME-01：issue_date 晚于批次导入基准日 → error。"""
    if not card.issue_date:
        return []  # 主键字段缺失由解析层负责，规则不越权
    anchor = _anchor_of(card, ctx)
    issue = _as_date(card.issue_date)
    if anchor is None or issue is None:
        return []  # 锚点/日期不可解析，不硬判
    if issue <= anchor:
        return []
    return [
        Finding(
            rule_id="R-TIME-01",
            level="error",
            invoice_numbers=[card.invoice_number],
            message="开票日期 %s 晚于批次 %s 报销基准日 %s，时间逻辑异常"
                    % (card.issue_date, card.batch_id or "-", anchor.isoformat()),
            evidence={
                "issue_date": card.issue_date,
                "anchor": anchor.isoformat(),
                "batch_id": card.batch_id,
                "delta_days": (issue - anchor).days,
            },
        )
    ]


def check_stale_period(card: InvoiceCard, ctx: Dict[str, Any]) -> List[Finding]:
    """R-TIME-02：issue 早于批次基准月份超过 N 期（仅追溯方向）→ review。"""
    if not card.issue_date:
        return []
    anchor = _anchor_of(card, ctx)
    issue = _as_date(card.issue_date)
    if anchor is None or issue is None:
        return []
    n_period = int(ctx["params"].get("time_n_period", DEFAULT_N_PERIOD))
    months_behind = (anchor.year * 12 + anchor.month) - (issue.year * 12 + issue.month)
    if months_behind <= n_period:
        return []
    return [
        Finding(
            rule_id="R-TIME-02",
            level="review",
            invoice_numbers=[card.invoice_number],
            message="开票日期 %s 距批次 %s 报销基准月 %04d-%02d 跨 %d 期（超过 %d 期），"
                    "跨期报销待人工确认"
                    % (card.issue_date, card.batch_id or "-",
                       anchor.year, anchor.month, months_behind, n_period),
            evidence={
                "issue_date": card.issue_date,
                "anchor": anchor.isoformat(),
                "batch_id": card.batch_id,
                "months_behind": months_behind,
                "n_period": n_period,
            },
        )
    ]
