"""版本号单一来源守门（M7，D11）：pyproject.toml 与 __version__ 必须一致。

事实（改前）：版本号两处手写——`pyproject.toml` 的 `version = "..."` 与
`src/invoice_ledger_checker/__init__.py` 的 `__version__ = "..."`；
`tests/test_package.py` 只锁 `__init__` 的字面值，pyproject 改错不会有任何提示。

本测试补上「两处必须相等」这一半；`test_package.py` 的硬编码断言保留
（它锁的是"值本身"，与本文的"两处一致"互补：一次漂移至少被两者之一抓住）。
"""

import re
from pathlib import Path

import invoice_ledger_checker

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert match, "pyproject.toml 缺 [project] version（正则未命中，措辞可能被改）"
    return match.group(1)


def test_version_matches_pyproject():
    declared = _pyproject_version()
    assert invoice_ledger_checker.__version__ == declared, (
        "版本号两处不一致：pyproject.toml = %r，__init__.__version__ = %r"
        % (declared, invoice_ledger_checker.__version__))


def test_version_is_pep440_style():
    """形如 X.Y.Z（可选本地/预发布后缀），拒绝 0.1 / v0.1.0 这类写法。"""
    version = _pyproject_version()
    assert re.match(r"^\d+\.\d+\.\d+", version), \
        "pyproject version = %r 不是 X.Y.Z 形态" % version
    assert not version.startswith("v"), "版本号不应带 v 前缀（tag 才带）"


def test_version_not_leaked_as_hardcoded_string_elsewhere():
    """除 pyproject 与 __init__ 外，src/ 不应再出现另一处版本字面量。"""
    version = _pyproject_version()
    pattern = re.compile(r"""__version__\s*=\s*["']%s["']""" % re.escape(version))
    hits = []
    for path in (REPO_ROOT / "src").rglob("*.py"):
        if path.name == "__init__.py" and path.parent.name == "invoice_ledger_checker":
            continue  # 允许的唯一字面量出处
        if pattern.search(path.read_text(encoding="utf-8")):
            hits.append(str(path.relative_to(REPO_ROOT)))
    assert not hits, "版本号在 pyproject/__init__ 之外还有硬编码：%s" % hits
