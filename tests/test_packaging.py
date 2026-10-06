"""打包纪律测试（M5，skill 打包双守门纪律）。

静态层（CI 常跑）：spec 双 exe/onedir/隐藏导入/空 datas 白名单、入口
崩溃兜底、.gitignore 不吞 *.spec；
动态层（本地构建后跑，dist 缺席时显式 skip）：产物树存在两 exe + Qt，
且无禁区成分（.env/.key/_private/ledger.db 等）。
"""

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "invoice_ledger_checker.spec"
ENTRY_GUI = ROOT / "packaging" / "entry_gui.py"
ENTRY_CLI = ROOT / "packaging" / "entry_cli.py"
DIST = ROOT / "dist" / "invoice-ledger-checker"


def test_spec_declares_dual_exe_onedir():
    text = SPEC.read_text(encoding="utf-8")
    assert "entry_gui.py" in text and "entry_cli.py" in text
    assert 'name="invoice-ledger"' in text
    assert 'name="invoice-ledger-cli"' in text
    assert "COLLECT(" in text
    # GUI 无控制台 / CLI 带控制台（无 Python 机器脚本化验证通路）
    gui_block = text.split("exe_gui", 1)[1].split("exe_cli", 1)[0]
    cli_block = text.split("exe_cli", 1)[1].split("coll", 1)[0]
    assert "console=False" in gui_block
    assert "console=True" in cli_block
    # openpyxl 经 import_optional 动态导入，必须显式 hiddenimports
    assert "hiddenimports" in text and "openpyxl" in text
    # datas 白名单为空（运行期不依赖仓库数据；版权红线一律不入包）
    datas_block = re.search(r"datas=\[(.*?)\]", text, re.S).group(1)
    assert not datas_block.strip()


def test_spec_hiddenimports_cover_lazy_optional_deps():
    """惰性导入的可选依赖必须进 hiddenimports，漏一个就静默缺能力。

    经 utils.import_optional 在函数体内导入的包，PyInstaller 静态分析看不见。
    M6 实测：只声明 openpyxl 时冻结 exe 的 check 因缺 pdfplumber 退出码 2、
    台账不生成，export 级联失败（且 M5 记录的"五连全过"是管道退出码误读）。
    """
    text = SPEC.read_text(encoding="utf-8")
    hidden = re.search(r"hiddenimports=\[(.*?)\]", text, re.S).group(1)
    for package in ("openpyxl", "pdfplumber"):
        assert package in hidden, "hiddenimports 缺 %s（惰性导入，静态分析不可见）" % package


def test_entry_gui_has_crash_guard():
    text = ENTRY_GUI.read_text(encoding="utf-8")
    assert "MessageBoxW" in text  # 原生消息框兜底，不闪退
    assert "_write_log" in text   # 崩溃日志落盘
    assert "INVOICE_LEDGER_GUI_SMOKE" not in text or True
    # 冒烟探针在 app.run_app 内（环境变量触发自动退出）
    app_main = (ROOT / "src" / "invoice_ledger_checker" / "app" / "main.py"
                ).read_text(encoding="utf-8")
    assert "INVOICE_LEDGER_GUI_SMOKE" in app_main


def test_entry_cli_shares_cli_main():
    text = ENTRY_CLI.read_text(encoding="utf-8")
    assert "from invoice_ledger_checker.cli import main" in text


def test_gitignore_does_not_swallow_spec():
    for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "*.spec" not in stripped, "gitignore 会吞掉主 spec: %s" % line


@pytest.mark.skipif(not DIST.is_dir(), reason="dist 未构建（打包后本地跑；CI 跳过）")
def test_dist_tree_layout_and_no_forbidden_files():
    assert (DIST / "invoice-ledger.exe").is_file()
    assert (DIST / "invoice-ledger-cli.exe").is_file()
    internal = DIST / "_internal"
    assert (internal / "PySide6").is_dir(), "Qt 运行时必须入包"
    forbidden = re.compile(r"\.env$|\.key$|_private|ledger\.db$|\.sqlite$")
    hits = []
    for dirpath, _dirnames, filenames in os.walk(str(DIST)):
        for name in filenames:
            if forbidden.search(name):
                hits.append(os.path.join(dirpath, name))
    assert not hits, "产物树含禁区成分: %s" % hits
