"""R-SEQ-01 连号拆分簇（plan/04 §3；M3 全量交付）。

同 seller_tax_id 分组，发票号码后缀（默认末 8 位）连续 ≥min_len 张且开票
日期跨度在窗口内 → suspicious。前缀不同只警示不判异常（M3 实现定稿：
跨前缀不产出 finding，防误报——见 plan/04 §3 规则表注）。

真值对齐（generator/synthetic.py 模块注释 §4）：基线号码后缀间隔 ≥2，
连号簇仅由 INJ-SEQ 产生；簇内日期跨度 ≤7 天。
"""

from datetime import date
from typing import Any, Dict, List, Tuple

from ...models import InvoiceCard
from ..engine import Finding

DEFAULT_SUFFIX_LEN = 8
DEFAULT_MIN_LEN = 3
DEFAULT_DATE_WINDOW_DAYS = 7


def _as_date(text: str):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def check_sequence_cluster(cards: List[InvoiceCard], ctx: Dict[str, Any]) -> List[Finding]:
    params = ctx["params"]
    suffix_len = int(params.get("seq_suffix_len", DEFAULT_SUFFIX_LEN))
    min_len = int(params.get("seq_min_len", DEFAULT_MIN_LEN))
    window_days = int(params.get("seq_date_window_days", DEFAULT_DATE_WINDOW_DAYS))

    groups: Dict[str, List[Tuple[int, str, str, InvoiceCard]]] = {}
    for card in cards:
        if not card.seller_tax_id or len(card.invoice_number) <= suffix_len:
            continue
        suffix_text = card.invoice_number[-suffix_len:]
        if not suffix_text.isdigit():
            continue  # 后缀非纯数字无法判定连续性，不硬判
        day = _as_date(card.issue_date)
        if day is None:
            continue  # 开票日期不可解析，无法判定窗口，不硬判
        prefix = card.invoice_number[:-suffix_len]
        groups.setdefault(card.seller_tax_id, []).append(
            (int(suffix_text), prefix, card.issue_date, card))

    findings = []
    for seller_tax_id, members in sorted(groups.items()):
        members.sort(key=lambda m: (m[0], m[2], m[3].invoice_number))
        run: List[Tuple[int, str, str, InvoiceCard]] = []
        stretches: List[List[Tuple[int, str, str, InvoiceCard]]] = []
        for member in members:
            if run and member[0] == run[-1][0] + 1:
                run.append(member)
            else:
                if len(run) >= 2:
                    stretches.append(run)
                run = [member]
        if len(run) >= 2:
            stretches.append(run)

        for stretch in stretches:
            if len(stretch) < min_len:
                continue
            prefixes = {m[1] for m in stretch}
            if len(prefixes) > 1:
                continue  # 前缀不同只警示不判异常（M3 定稿：不产出 finding）
            days = [m[2] for m in stretch]
            span = (_as_date(max(days)) - _as_date(min(days))).days
            if span > window_days:
                continue
            numbers = sorted(m[3].invoice_number for m in stretch)
            findings.append(Finding(
                rule_id="R-SEQ-01",
                level="suspicious",
                invoice_numbers=numbers,
                message="同销售方 %s 的 %d 张发票号码连续（日期跨度 %d 天），疑似连号拆分报销"
                        % (stretch[0][3].seller_name or seller_tax_id,
                           len(stretch), span),
                evidence={
                    "seller_tax_id": seller_tax_id,
                    "count": len(stretch),
                    "date_span_days": span,
                    "batches": sorted({m[3].batch_id for m in stretch}),
                },
            ))
    return findings
