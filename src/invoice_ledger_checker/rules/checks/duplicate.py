"""判重三规则：R-DUP-01 精确重复 / R-DUP-02 联合键再制票 / R-DUP-03 模糊重复。

语义权威出处：generator/synthetic.py 模块注释 §3/§4 与 plan/04 §3（M3 定稿）：
- 入库与判重分离：引擎输入 = 全部解析卡（含入库被拒的同号副本）；
  R-DUP-01 = 本次导入集合内同号多卡 或 号码已存在台账（ctx existing_numbers）。
- R-DUP-02 排除纯复制件（EXACT 只报 01，JOINT 报 02+01）：纯复制件判定 =
  两卡语义字段全等，evidence/confidence/field_flags/batch_id 不参与比较
  （与解析对账口径一致，benchmarks/field_match.py）。
- R-DUP-03 门控互斥：排除已命中 R-DUP-01/02 的号码组合（引擎按注册顺序
  执行并经 ctx["findings"] 传递已命中集，plan/04 §3.1）；金额 = total_with_tax，
  amount_tol=0.00 精确匹配档。
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Set, Tuple

from ...models import InvoiceCard
from ..engine import Finding

DEFAULT_DATE_WINDOW_DAYS = 1
DEFAULT_AMOUNT_TOL = "0.00"

# 纯复制件判定不参与比较的字段（解析层自由度 + 入库时填充项）
_NON_SEMANTIC_FIELDS = frozenset(("batch_id", "confidence", "field_flags", "evidence"))


def _semantic_dict(card: InvoiceCard) -> Dict[str, Any]:
    payload = card.to_dict()
    return {k: v for k, v in payload.items() if k not in _NON_SEMANTIC_FIELDS}


def _as_date(text: str):
    from datetime import date

    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _hit_numbers(ctx: Dict[str, Any], rule_ids: Tuple[str, ...]) -> Set[str]:
    """已命中指定规则的号码全集（R-DUP-03 门控输入，plan/04 §3）。"""
    hits: Set[str] = set()
    for finding in ctx.get("findings", []):
        if finding.rule_id in rule_ids:
            hits.update(finding.invoice_numbers)
    return hits


def check_in_batch_duplicate(cards: List[InvoiceCard], ctx: Dict[str, Any]) -> List[Finding]:
    """R-DUP-01 精确重复：同号多卡（含被拒副本）或号码已存在台账 → error。"""
    existing: Set[str] = set(ctx.get("existing_numbers") or ())
    groups: Dict[str, List[InvoiceCard]] = {}
    for card in cards:
        groups.setdefault(card.invoice_number, []).append(card)
    findings = []
    for number in sorted(groups):
        members = groups[number]
        pre_existing = number in existing
        if len(members) < 2 and not pre_existing:
            continue
        findings.append(Finding(
            rule_id="R-DUP-01",
            level="error",
            invoice_numbers=[number],
            message="发票号码重复：%s出现 %d 次%s，疑似重复报销"
                    % ("台账已有记录且本次" if pre_existing else "本次导入中",
                       len(members), "（台账既有号码）" if pre_existing else ""),
            evidence={
                "occurrences": len(members),
                "batches": sorted({m.batch_id for m in members}),
                "pre_existing_in_ledger": pre_existing,
            },
        ))
    return findings


def check_joint_key_duplicate(cards: List[InvoiceCard], ctx: Dict[str, Any]) -> List[Finding]:
    """R-DUP-02 联合键重复：同号+同价税合计+同开票日期、跨批次且非纯复制件 → error。"""
    groups: Dict[str, List[InvoiceCard]] = {}
    for card in cards:
        groups.setdefault(card.invoice_number, []).append(card)
    findings = []
    for number in sorted(groups):
        members = groups[number]
        pair_evidence = []
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                first, second = members[i], members[j]
                if first.batch_id == second.batch_id:
                    continue  # 联合键语义要求登记来源（批次）不同
                if not (first.total_with_tax == second.total_with_tax
                        and first.issue_date == second.issue_date):
                    continue
                if _semantic_dict(first) == _semantic_dict(second):
                    continue  # 纯复制件由 R-DUP-01 完整覆盖（真值语义 M1 定稿）
                pair_evidence.append({
                    "batches": sorted([first.batch_id, second.batch_id]),
                    "total_with_tax": first.total_with_tax,
                    "issue_date": first.issue_date,
                })
        if pair_evidence:
            findings.append(Finding(
                rule_id="R-DUP-02",
                level="error",
                invoice_numbers=[number],
                message="联合键重复（号码+价税合计+开票日期相同、批次不同且内容有差异），"
                        "疑似跨批次再制票",
                evidence={"pairs": pair_evidence},
            ))
    return findings


def check_fuzzy_duplicate(cards: List[InvoiceCard], ctx: Dict[str, Any]) -> List[Finding]:
    """R-DUP-03 模糊重复：同销售方 ±date_window 日内金额相等的不同号票 → suspicious。

    门控：排除已命中 R-DUP-01/02 的号码组合（同号副本不参与配对）。
    """
    params = ctx["params"]
    window_days = int(params.get("dup_date_window_days", DEFAULT_DATE_WINDOW_DAYS))
    amount_tol = Decimal(str(params.get("dup_amount_tol", DEFAULT_AMOUNT_TOL)))
    gated = _hit_numbers(ctx, ("R-DUP-01", "R-DUP-02"))

    dated: List[Tuple[InvoiceCard, Any]] = []
    for card in cards:
        if not card.seller_tax_id or card.invoice_number in gated:
            continue
        day = _as_date(card.issue_date)
        try:
            total = Decimal(card.total_with_tax)
        except InvalidOperation:
            continue  # 金额不可比，不硬判
        if day is not None:
            dated.append((card, day))

    findings = []
    for i in range(len(dated)):
        for j in range(i + 1, len(dated)):
            first_card, first_day = dated[i]
            second_card, second_day = dated[j]
            if first_card.invoice_number == second_card.invoice_number:
                continue  # 同号组合属 R-DUP-01 辖区（已门控，双保险）
            if first_card.seller_tax_id != second_card.seller_tax_id:
                continue
            if abs((first_day - second_day).days) > window_days:
                continue
            if abs(Decimal(first_card.total_with_tax)
                   - Decimal(second_card.total_with_tax)) > amount_tol:
                continue
            numbers = sorted([first_card.invoice_number, second_card.invoice_number])
            findings.append(Finding(
                rule_id="R-DUP-03",
                level="suspicious",
                invoice_numbers=numbers,
                message="同销售方 %s 在 %d 天内出现价税合计相同的不同发票，疑似近似重复报销"
                        % (first_card.seller_name or first_card.seller_tax_id, window_days),
                evidence={
                    "seller_tax_id": first_card.seller_tax_id,
                    "amount": first_card.total_with_tax,
                    "issue_dates": sorted([first_card.issue_date, second_card.issue_date]),
                    "batches": sorted([first_card.batch_id, second_card.batch_id]),
                },
            ))
    return findings
