"""桌面 GUI 主入口（M5 交付）。"""

from ..utils import import_optional


def run_app() -> int:
    """启动 PySide6 应用。M5 交付；当前仅做依赖门 + 结构桩。"""
    import_optional("PySide6", "desktop")
    raise NotImplementedError("桌面 GUI 属 M5 交付（plan/05 里程碑）；骨架未实现。")
