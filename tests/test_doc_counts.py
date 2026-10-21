"""README 测试数口径守门（M7）：文档里每个「N 收集」都与其实际收集数一致。

背景（D3）：README 曾把「全量 179 项测试」与 `pip install -e ".[dev]"` 写在同一
代码块——照抄实得 169 收集 / 152 passed + 18 skipped（差 10 = test_app.py 的 GUI
用例整模块不进收集列表）。数字从此必须有门。

判定口径：
- 用 subprocess 跑 `pytest --co -q -o addopts=""` 取**当前环境**的收集数
  （`-o addopts=""` 是必须的：本仓 addopts="-q"，再传 -q 会变 -qq 吞掉汇总行）；
- 按当前环境是否装齐重依赖判定走 README 的哪一条口径（.[dev] 还是 .[all]）；
- 断言该条目的「收集数」与实测相等，并静态校验该行的 passed/skipped 算术自洽
  （.[all]：passed == 收集数且 skipped == 0；.[dev]：passed + skipped == 收集数 + 1，
  其中 +1 是 test_app.py 模块级 importorskip 产生的那条模块级 skip——它不进收集
  列表，却是 skip 计数里的一条）。

README 措辞一变（比如把「183 收集」改成别的写法）本测试就解析失败并报清晰错误，
提示同步改测试——这是有意的耦合：数字和命令必须待在一起。
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

# 两种口径的 README 行（措辞即契约；改措辞须同步本测试）
_COLLECTED_RE = re.compile(r"\*{0,2}\s*(\d+)\s*收集")
_OUTCOME_RE = re.compile(r"(\d+) passed \+ (\d+) skipped")

_HEAVY_MODULES = ("PySide6", "pdfplumber", "openpyxl", "reportlab", "docx")


def _readme_text() -> str:
    return README.read_text(encoding="utf-8")


def _collect_count() -> int:
    """当前环境的测试收集数（子进程，避免污染本进程的 pytest 状态）。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--co", "-q", "-o", "addopts="],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, (
        "收集数探针失败（rc=%s）\n%s\n%s"
        % (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:]))
    match = re.search(r"(\d+) tests? collected", proc.stdout + proc.stderr)
    assert match, "pytest --co 未输出收集数，无法守门：\n%s" % proc.stdout[-2000:]
    return int(match.group(1))


def _missing_heavy_modules() -> list:
    import importlib.util

    return [name for name in _HEAVY_MODULES
            if importlib.util.find_spec(name) is None]


def _profile_lines():
    """按 README 出现顺序返回 [(收集数, passed, skipped, 原始行)]。"""
    lines = []
    for raw in _readme_text().splitlines():
        collected = _COLLECTED_RE.search(raw)
        outcome = _OUTCOME_RE.search(raw)
        if collected and outcome:
            lines.append((int(collected.group(1)), int(outcome.group(1)),
                          int(outcome.group(2)), raw.strip()))
    return lines


def test_readme_declares_both_profiles():
    """README 必须有 .[dev] 与 .[all] 两条带数字的口径（措辞变了要同步本测试）。"""
    lines = _profile_lines()
    assert len(lines) >= 2, (
        "README 应有两处「N 收集 / M passed + K skipped」口径（.[dev] 与 .[all]）；"
        "实测匹配到 %d 处。改措辞请同步 tests/test_doc_counts.py" % len(lines))
    text = _readme_text()
    assert 'pip install -e ".[dev]"' in text
    assert 'pip install -e ".[all]"' in text


def test_all_profile_arithmetic_is_self_consistent():
    """.[all] 那一行必须 passed == 收集数、skipped == 0（全 extras 无跳过）。"""
    lines = _profile_lines()
    full = [entry for entry in lines if entry[2] == 0]
    assert full, "README 缺「skipped 为 0」的全 extras 口径行"
    for collected, passed, skipped, raw in full:
        assert passed == collected, (
            "全 extras 口径算术不自洽：收集 %d 但 passed %d\n行: %s"
            % (collected, passed, raw))


def test_dev_profile_arithmetic_counts_module_level_skip():
    """. [dev] 口径：passed + skipped == 收集数 + 1（test_app.py 模块级 skip）。"""
    with_skips = [entry for entry in _profile_lines() if entry[2] > 0]
    assert with_skips, "README 缺「含 skipped」的 dev 口径行"
    for collected, passed, skipped, raw in with_skips:
        assert passed + skipped == collected + 1, (
            "dev 口径算术不自洽：收集 %d，passed %d + skipped %d = %d（应为 %d）\n行: %s"
            % (collected, passed, skipped, passed + skipped, collected + 1, raw))


def test_readme_collected_count_matches_current_environment():
    """README 的收集数必须与当前环境实测一致（按装了哪些 extras 选对应口径）。"""
    measured = _collect_count()
    missing = _missing_heavy_modules()
    candidates = [entry[0] for entry in _profile_lines()]
    if missing:
        expected = min(candidates)  # 最小口径 = .[dev]
        profile = ".[dev]（缺 %s）" % "、".join(missing)
    else:
        expected = max(candidates)  # 全 extras 口径 = .[all]
        profile = ".[all]（重依赖齐备）"
    assert measured == expected, (
        "README 收集数与实测不一致：README（%s）= %d，实测 = %d。"
        "改测试或改 README 后请同步 tests/test_doc_counts.py 的口径说明"
        % (profile, expected, measured))


def test_doc_profiles_differ_by_gui_module_when_desktop_missing():
    """两个口径的差值必须等于 GUI 模块的用例数（缺 PySide6 时整模块不进收集）。

    这是把 D3 的教训钉死：差值不是 0、也不是 skip 数，而是 test_app.py 的用例数。
    """
    candidates = sorted({entry[0] for entry in _profile_lines()})
    if len(candidates) < 2:
        pytest.skip("README 只声明了一种口径，无差值可比")
    gap = candidates[-1] - candidates[0]
    app_module = (REPO_ROOT / "tests" / "test_app.py").read_text(encoding="utf-8")
    app_tests = len(re.findall(r"^def test_", app_module, re.M))
    assert gap == app_tests, (
        "README 两种口径相差 %d，但 tests/test_app.py 有 %d 个用例——"
        "差值应恰好是 GUI 模块用例数（模块级 importorskip 整模块不进收集）"
        % (gap, app_tests))
