"""extras 覆盖断言测试（M5，plan/03 §4 纪律的回归锁）。

两层：
1. 静态层——pyproject extras 必须覆盖各组件运行期真实 import 的包
   （openpyxl/PySide6/PySide6-Addons/pyinstaller…），漏声明即本测试红；
2. 动态层——模拟缺依赖运行期路径：export 组件与 cli app 命令必须抛/退
   出"带安装提示"的失败（exit 2），不裸崩。

py3.8 无 tomllib：extras 块用正则解析（CI/干净环境同路径）。
"""

import importlib
import io
import re
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from invoice_ledger_checker.cli import main as cli_main
from invoice_ledger_checker.utils import OptionalDependencyError

PYPROJECT = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
    encoding="utf-8")

# 组件运行期 import -> 必须落入的 extra（权威映射；新增 import 同步登记）
RUNTIME_IMPORT_EXTRA = {
    "openpyxl": "export",
    "pyside6": "desktop",
    "pyside6-addons": "desktop",
    "pdfplumber": "parse",
    "reportlab": "data",
    "python-docx": "report",
    "pytest": "dev",
    "pyinstaller": "pack",
}


def _extras_blocks():
    """解析 [project.optional-dependencies] 各 extra 的依赖 spec 列表。"""
    match = re.search(
        r"\[project\.optional-dependencies\](.*?)(?=^\[)", PYPROJECT,
        re.S | re.M)
    assert match, "pyproject.toml 缺 [project.optional-dependencies] 节"
    blocks = {}
    for name, body in re.findall(r"^(\w+)\s*=\s*\[(.*?)\]", match.group(1),
                                 re.S | re.M):
        specs = re.findall(r'"([^"]+)"', body)
        blocks[name] = {
            re.match(r"[A-Za-z0-9_.\-]+", spec).group(0).lower()
            .replace("_", "-")
            for spec in specs
        }
    return blocks


def test_extras_cover_runtime_imports():
    blocks = _extras_blocks()
    for package, extra in RUNTIME_IMPORT_EXTRA.items():
        assert extra in blocks, "pyproject 缺 extra 组 [%s]" % extra
        assert package in blocks[extra], (
            "包 %s 的运行期 import 未被 extras [%s] 声明" % (package, extra))


def test_all_extra_composition():
    """all = dev+parse+data+export+report+desktop（pack 不进 all：打包机
    独立装机，CI 测试矩阵保持精简——改此口径须同步 HANDOFF）。"""
    blocks = _extras_blocks()
    all_body = re.search(r"^all\s*=\s*\[(.*?)\]", PYPROJECT,
                         re.S | re.M).group(1)
    referenced = set(re.findall(r"[\w-]+", all_body)) - {"invoice-ledger-checker"}
    assert referenced == {"dev", "parse", "data", "export", "report", "desktop"}
    assert "pack" not in referenced


def test_desktop_locked_below_67_on_py38():
    """py<3.9 锁 <6.7（6.7+ 无 cp38 wheel，M5 实测回写 plan/03）。"""
    desktop_section = re.search(r"desktop\s*=\s*\[(.*?)\]", PYPROJECT,
                                re.S).group(1)
    py38_lines = [line for line in desktop_section.splitlines()
                  if "python_version < '3.9'" in line]
    assert py38_lines, "desktop extras 缺 py<3.9 环境标记行"
    assert all("<6.7" in line for line in py38_lines)


def test_reportlab_locked_below_4():
    """data extras 锁 reportlab <4。

    两个理由（M6 干净环境实测）：
    ① 4.x 调用 hashlib.md5(usedforsecurity=False)，该参数 py3.9 才有——在 3.8 上
       generate 直接 TypeError 崩（README 的 generate 步骤与 CI 的 win-3.8 作业同挂）；
    ② 入仓冻结数据集由 3.6.13 产出，生成器有位级复现门（tests/test_generator.py），
       产出库版本属契约的一部分——放开上界会让"同 seed 逐字节一致"失守。
    """
    data_section = re.search(r"^data\s*=\s*\[(.*?)\]", PYPROJECT,
                             re.S | re.M).group(1)
    assert "<4" in data_section, "data extras 的 reportlab 未锁 <4（3.8 运行时崩溃）"


def test_missing_openpyxl_raises_install_hint(tmp_path, monkeypatch):
    """动态层：缺 openpyxl 时导出组件抛带安装提示的异常（不裸 ImportError）。"""
    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name == "openpyxl":
            raise ImportError("No module named %r (simulated)" % name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    from invoice_ledger_checker.export.excel import export_ledger

    db = tmp_path / "ledger.db"
    from invoice_ledger_checker.storage import Ledger

    ledger = Ledger(str(db))
    ledger.close()
    with pytest.raises(OptionalDependencyError) as excinfo:
        export_ledger(str(db), str(tmp_path / "out.xlsx"))
    assert "[export]" in str(excinfo.value)


def test_missing_pyside_cli_app_exits_two(monkeypatch, capsys):
    """动态层：缺 PySide6 时 `app` 命令退出码 2 + 安装提示（CLI 契约）。"""
    real_import = importlib.import_module

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("No module named %r (simulated)" % name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(["app"])
    out = buf.getvalue()
    assert code == 2
    assert "PySide6" in out
    assert "desktop" in out


def test_missing_pyside6_qtcharts_hint(monkeypatch):
    """QtCharts（PySide6-Addons）单独门一次，报错定位到 desktop extras。

    需 PySide6 在场才能模拟"QtCharts 缺失"路径（无 desktop extras 环境
    整体跳过——app 通路本身已由 test_app.py 的模块级 skip 计数覆盖）。
    """
    pytest.importorskip("PySide6")
    real_import = importlib.import_module
    import sys as _sys

    pyside = real_import("PySide6")

    def fake_import(name, *args, **kwargs):
        if name == "PySide6.QtCharts":
            raise ImportError("No module named %r (simulated)" % name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    saved = _sys.modules.pop("PySide6.QtCharts", None)
    try:
        from invoice_ledger_checker.cli import _cmd_app
        import argparse

        with pytest.raises(OptionalDependencyError) as excinfo:
            _cmd_app(argparse.Namespace(db=":memory:"))
        assert "[desktop]" in str(excinfo.value)
    finally:
        if saved is not None:
            _sys.modules["PySide6.QtCharts"] = saved
        assert pyside is not None
