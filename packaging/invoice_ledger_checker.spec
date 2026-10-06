# -*- mode: python ; coding: utf-8 -*-
"""invoice-ledger-checker 主打包 spec（PyInstaller 6.x，onedir 双 exe）。

- 打包机 = win-3.8 CI 同环境：Python 3.8.8 + PyInstaller >=6,<7（实测
  6.22.3）+ PySide6 6.6.3.1（cp38-abi3，plan/03 §3 已复核）；
- onedir 双 exe：invoice-ledger（GUI，console=False，双击即用）+
  invoice-ledger-cli（console=True，无 Python 机器的脚本化验证通路：
  doctor/demo/generate/check/export/benchmark 全可跑）；
- datas 白名单为空：运行期不需要仓库内数据（demo 自含合成数据、
  check/export 消费用户输入）—— 版权红线数据一律不入包；
- hiddenimports：openpyxl 经 utils.import_optional 动态导入，静态分析
  不可见，必须显式声明；
- 构建命令（仓库根）：pyinstaller packaging/invoice_ledger_checker.spec
  （需 extras: pack；dev 环境另装 parse/data/export/desktop 供分析捕获）。
"""

import os

ROOT = os.path.abspath(SPECPATH + "/..")  # SPECPATH 解析到 spec 所在目录，非 CWD
SRC = os.path.join(ROOT, "src")
ENTRY_GUI = os.path.join(SPECPATH, "entry_gui.py")
ENTRY_CLI = os.path.join(SPECPATH, "entry_cli.py")

a = Analysis(
    [ENTRY_GUI, ENTRY_CLI],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=["openpyxl"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)


def _script_entry(name):
    """按名字取入口脚本条目。

    注意：a.scripts 还包含 PyInstaller 运行时钩子（pyiboot01_bootstrap /
    pyi_rth_*），按下标取会拿到钩子——bootloader 跑完钩子即静默退出
    （M5 实录：RC=0 无输出的假成功）。必须按脚本名过滤。
    """
    for entry in a.scripts:
        if name in str(entry[0]) or name in os.path.basename(str(entry[1])):
            return [entry]
    raise SystemExit("Analysis 结果中找不到入口脚本: %s" % name)


exe_gui = EXE(
    pyz,
    _script_entry("entry_gui"),
    exclude_binaries=True,
    name="invoice-ledger",
    console=False,
    disable_windowed_traceback=False,
)
exe_cli = EXE(
    pyz,
    _script_entry("entry_cli"),
    exclude_binaries=True,
    name="invoice-ledger-cli",
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe_gui,
    exe_cli,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="invoice-ledger-checker",
)
