"""检测规则引擎：注册-执行-产出 Finding（契约权威出处 plan/04 §3）。

- 级别语义：error=确认异常（确定性算术/键冲突）；suspicious=疑似（模糊/簇类
  启发）；review=待人工确认（低置信度、跨期临界）。多值/低置信度不硬判。
- 规则分两类 scope：card（逐卡）与 batch（跨卡，如批内判重）。
- 执行顺序 = 注册顺序；ctx["findings"] 传递已命中集——后续规则据此做
  显式互斥（plan/04 §3：R-DUP-03 必须排除已命中 R-DUP-01/02 的组合）。
- 数值结论永远来自确定性规则；引擎零第三方依赖（评测零 API 的前提）。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..models import InvoiceCard

LEVELS = ("error", "suspicious", "review")

CardRuleFunc = Callable[[InvoiceCard, Dict[str, Any]], List["Finding"]]
BatchRuleFunc = Callable[[List[InvoiceCard], Dict[str, Any]], List["Finding"]]


@dataclass
class Finding:
    """异常记录（入库形态见 storage.findings 表）。"""

    rule_id: str
    level: str
    invoice_numbers: List[str]
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    finding_id: str = ""  # 空表示未持久化；engine.run 时确定性生成

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "level": self.level,
            "invoice_numbers": list(self.invoice_numbers),
            "message": self.message,
            "evidence": dict(self.evidence),
        }


@dataclass
class Rule:
    rule_id: str
    name: str
    level: str
    scope: str            # "card" | "batch"
    func: Callable       # (card, ctx) -> [Finding] | (cards, ctx) -> [Finding]

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError("非法判定级别 %r（须为 %s）" % (self.level, "/".join(LEVELS)))
        if self.scope not in ("card", "batch"):
            raise ValueError("非法 scope %r（须为 card/batch）" % self.scope)


class DetectionEngine:
    """按注册顺序执行规则；规则 ID 全局唯一。"""

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        self.params: Dict[str, Any] = dict(params or {})
        self._rules: List[Rule] = []
        self._by_id: Dict[str, Rule] = {}

    def register(self, rule: Rule) -> None:
        if rule.rule_id in self._by_id:
            raise ValueError("规则 ID 重复注册: %s" % rule.rule_id)
        self._rules.append(rule)
        self._by_id[rule.rule_id] = rule

    @property
    def rule_ids(self) -> List[str]:
        """按注册顺序的规则 ID（报告/演示展示用）。"""
        return [r.rule_id for r in self._rules]

    def run(self, cards: List[InvoiceCard],
            ctx_extra: Optional[Dict[str, Any]] = None) -> List[Finding]:
        """执行全部规则；ctx_extra 合入规则上下文（契约见 plan/04 §3.1）。

        可用键：batch_anchors（batch_id -> ISO 日期，R-TIME 基准通路）、
        default_anchor（无批次映射时的导入日期）、existing_numbers（台账
        既有号码集，R-DUP-01 持久判重输入）。
        """
        ctx: Dict[str, Any] = {"params": self.params, "findings": []}
        if ctx_extra:
            ctx.update(ctx_extra)
        results: List[Finding] = []
        seen = set()
        for rule in self._rules:
            if rule.scope == "batch":
                found = rule.func(cards, ctx)
            else:
                found = []
                for card in cards:
                    found.extend(rule.func(card, ctx))
            for finding in found:
                if finding.rule_id != rule.rule_id:
                    raise ValueError(
                        "规则 %s 的 check 产出了 %s 的 finding" % (rule.rule_id, finding.rule_id)
                    )
                if finding.level not in LEVELS:
                    raise ValueError("finding 非法级别: %r" % finding.level)
                if not finding.finding_id:
                    # 多号码 finding 号码全集入 ID，保证 findings 表主键唯一
                    finding.finding_id = "%s:%s" % (
                        finding.rule_id,
                        "|".join(finding.invoice_numbers) if finding.invoice_numbers else "-",
                    )
                key = (finding.finding_id, finding.message)
                if key in seen:
                    continue  # 同事实去重（幂等）
                seen.add(key)
                results.append(finding)
                ctx["findings"].append(finding)
        return results


def register_builtin(engine: DetectionEngine) -> None:
    """注册内置八规则（plan/04 §3.1 固定顺序；语义权威 generator/synthetic.py 模块注释）。"""
    from . import checks

    for rule in checks.builtin_rules():
        engine.register(rule)
