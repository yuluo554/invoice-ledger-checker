"""CLI 打包入口（PyInstaller console=True）。

与 GUI exe 共用同一 invoice_ledger_checker.cli:main——无 Python 机器上
的脚本化验证通路（doctor/demo/generate/check/export/benchmark 全可跑）。
"""

import sys

from invoice_ledger_checker.cli import main

if __name__ == "__main__":
    sys.exit(main())
