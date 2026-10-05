"""测试引导：把 src/ 加入 sys.path（开发期免安装跑 pytest）。

正式发布仍按 README 的 `pip install -e .[dev]` 路径验证（M6 干净环境门）；
本 bootstrap 只是让 CI 与本机无需安装即可收集测试。
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
