"""v0.2.0 六页签离屏截图（复用 M6 方法：offscreen + QFontDatabase 挂 CJK 字体）。

用法（仓根，build-venv312 或 il-venv 任一装齐 desktop extras 的解释器）：
    python make_m7_shots.py <db_path> <out_dir>

db_path 由 invoice-ledger check data/invoices --db <path> 产出（合成数据）。
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from invoice_ledger_checker.app.main import MainWindow  # noqa: E402

TABS = ["导入", "台账", "异常清单", "看板", "导出", "设置"]
# (显示名, MainWindow 属性名)——与 app/main.py 的 addTab 顺序一致
TAB_ATTRS = list(zip(TABS, ["import_tab", "ledger_tab", "findings_tab",
                            "dashboard_tab", "export_tab", "settings_tab"]))

CJK_CANDIDATES = [
    r"C:/Windows/Fonts/msyh.ttc",
    r"C:/Windows/Fonts/msyh.ttf",
    r"C:/Windows/Fonts/simhei.ttf",
    r"C:/Windows/Fonts/simsun.ttc",
]


def install_cjk_font(app):
    """离屏平台不带字体：必须 addApplicationFont + setFont，否则整屏方块。"""
    for path in CJK_CANDIDATES:
        if os.path.isfile(path):
            font_id = QFontDatabase.addApplicationFont(path)
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                app.setFont(QFont(families[0], 10))
                return path
    raise SystemExit("找不到可用的 CJK 字体，无法保证截图可读")


def main():
    db_path = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    app = QApplication([])
    font_path = install_cjk_font(app)
    window = MainWindow(db_path=db_path)
    window.resize(1280, 820)
    window.show()
    app.processEvents()
    for index, (name, attr) in enumerate(TAB_ATTRS):
        window.tabs.setCurrentIndex(index)
        for _ in range(8):
            app.processEvents()
        widget = getattr(window, attr)
        if attr == "findings_tab":
            # 选中第一条异常 -> 证据面板显示证据 + 「依据」（v0.2.0 新特性，截图要点）
            table = getattr(widget, "table", None)
            model = getattr(widget, "model", None)
            if table is not None and model is not None and model.rowCount() > 0:
                table.selectRow(0)
                table.setCurrentIndex(model.index(0, 0))
                for _ in range(6):
                    app.processEvents()
        # 抓整窗（含页签栏与状态栏——状态栏含数据库路径与免责声明，是产品形态的一部分）
        pixmap = window.grab()
        out = os.path.join(out_dir, "shot-%d-%s.png" % (index + 1, name))
        pixmap.save(out, "PNG")
        print("saved", out, pixmap.width(), "x", pixmap.height(), "font", font_path)


if __name__ == "__main__":
    main()