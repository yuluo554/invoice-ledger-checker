"""GUI 打包入口（PyInstaller console=False，双击即用）。

启动失败兜底（plan/03 §6）：依赖缺失/初始化异常时写日志 + 原生消息框
提示，不闪退。冒烟探针：环境变量 INVOICE_LEDGER_GUI_SMOKE=1 时窗口
显示后自动退出（干净环境无人值守验证 GUI 通路）。
"""

import os
import sys
import traceback

_LOG_NAME = "invoice-ledger-gui.log"


def _write_log(message: str) -> str:
    """日志写到 exe 旁边；目录只读时退回系统临时目录。返回实际路径。"""
    for base in (os.path.dirname(os.path.abspath(sys.executable)),
                 os.environ.get("TEMP") or os.getcwd()):
        try:
            path = os.path.join(base, _LOG_NAME)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(message)
            return path
        except OSError:
            continue
    return ""


def _alert(message: str) -> None:
    try:
        log_path = _write_log(message)
    except Exception:
        log_path = ""
    text = message
    if log_path:
        text += "\n\n详细信息已写入: %s" % log_path
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None, text, "invoice-ledger 启动失败", 0x10)
    except Exception:
        pass  # 连消息框都不可用时仅留日志


def main() -> int:
    try:
        from invoice_ledger_checker.app.main import run_app

        return run_app()
    except Exception:
        _alert("桌面应用启动失败：\n%s" % traceback.format_exc(limit=6))
        return 2


if __name__ == "__main__":
    sys.exit(main())
