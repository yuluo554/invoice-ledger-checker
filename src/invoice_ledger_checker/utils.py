"""跨模块小工具：编码防御与可选依赖惰性导入。

惰性导入纪律（plan/03 §4）：新增对重量级库的 import 必须走
import_optional，且 pyproject extras 声明同步覆盖，缺一不可。
"""

import importlib
import sys


class OptionalDependencyError(RuntimeError):
    """可选依赖缺失；异常消息自带安装提示，CLI 捕获后友好退出（码 2）。"""

    def __init__(self, module_name: str, extra: str) -> None:
        super().__init__(
            "缺少可选依赖 {mod}，请先安装：{hint}".format(
                mod=module_name, hint=install_hint(extra)
            )
        )
        self.module_name = module_name
        self.extra = extra


def install_hint(extra: str) -> str:
    return "py -m pip install -U pip && py -m pip install -e \".[%s]\"" % extra


def import_optional(module_name: str, extra: str):
    """惰性导入可选依赖；缺失时抛带安装提示的 OptionalDependencyError。"""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise OptionalDependencyError(module_name, extra) from exc


def force_utf8_stdio() -> None:
    """Windows 控制台默认 GBK：中文输出防崩（py3.7+ reconfigure）。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # 流已被接管/关闭等异常场景
            pass
