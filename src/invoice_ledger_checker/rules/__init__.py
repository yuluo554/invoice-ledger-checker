"""规则层：检测规则引擎与内置规则（契约见 plan/04 §3）。"""

from .engine import DetectionEngine, Finding, Rule, register_builtin

__all__ = ["DetectionEngine", "Finding", "Rule", "register_builtin"]
