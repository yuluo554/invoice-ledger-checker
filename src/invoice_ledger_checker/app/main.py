"""桌面 GUI 主入口（M5，plan/04 §6 六窗口组件）。

PySide6 多页签只消费既有 CLI/引擎 API（cli._scan_and_parse /
_run_check_pipeline）与 storage.Ledger 查询——不另起第二套行为。
免责声明常驻状态栏；退出码契约同 CLI（依赖缺失由 cli 捕获转 2）。
"""

import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QStatusBar, QTabWidget

from ..rules.checks.arithmetic import DEFAULT_TOLERANCE
from ..rules.checks.duplicate import DEFAULT_AMOUNT_TOL as DUP_AMOUNT_TOL
from ..rules.checks.duplicate import DEFAULT_DATE_WINDOW_DAYS as DUP_DATE_WINDOW_DAYS
from ..rules.checks.sequence import (
    DEFAULT_DATE_WINDOW_DAYS as SEQ_DATE_WINDOW_DAYS,
    DEFAULT_MIN_LEN as SEQ_MIN_LEN,
    DEFAULT_SUFFIX_LEN as SEQ_SUFFIX_LEN,
)
from ..rules.checks.time_rules import DEFAULT_N_PERIOD
from ..storage import Ledger
from .tabs import (
    DashboardTab,
    ExportTab,
    FindingsTab,
    ImportTab,
    LedgerTab,
    SettingsTab,
)

DISCLAIMER = ("免责声明：检测结论仅供人工复核参考，不构成审计意见；"
              "数据全离线本地处理，无网络请求。")

# 默认检测参数（FR-19）：单一来源 = 各规则模块 DEFAULT_* 常量
DEFAULT_ENGINE_PARAMS = {
    "arith_tolerance": DEFAULT_TOLERANCE,
    "dup_amount_tol": DUP_AMOUNT_TOL,
    "dup_date_window_days": DUP_DATE_WINDOW_DAYS,
    "seq_suffix_len": SEQ_SUFFIX_LEN,
    "seq_min_len": SEQ_MIN_LEN,
    "seq_date_window_days": SEQ_DATE_WINDOW_DAYS,
    "time_n_period": DEFAULT_N_PERIOD,
}


class AppContext:
    """GUI 共享状态：Ledger 连接 + 检测参数（设置页修改，下次导入生效）。"""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.ledger = Ledger(db_path)
        self.engine_params = dict(DEFAULT_ENGINE_PARAMS)

    def reopen(self, db_path: str) -> None:
        try:
            self.ledger.close()
        except Exception:
            pass
        self.db_path = db_path
        self.ledger = Ledger(db_path)


class MainWindow(QMainWindow):
    """主窗口：六页签 + 状态栏（数据库路径 + 免责声明常驻）。"""

    def __init__(self, db_path: str = "ledger.db") -> None:
        super().__init__()
        self.setWindowTitle("invoice-ledger 电子发票台账与重复报销检测")
        self.resize(1180, 760)
        self.ctx = AppContext(db_path)

        self.tabs = QTabWidget()
        self.import_tab = ImportTab(self.ctx)
        self.ledger_tab = LedgerTab(self.ctx)
        self.findings_tab = FindingsTab(self.ctx)
        self.dashboard_tab = DashboardTab(self.ctx)
        self.export_tab = ExportTab(self.ctx)
        self.settings_tab = SettingsTab(self.ctx)
        self.tabs.addTab(self.import_tab, "导入")
        self.tabs.addTab(self.ledger_tab, "台账")
        self.tabs.addTab(self.findings_tab, "异常清单")
        self.tabs.addTab(self.dashboard_tab, "看板")
        self.tabs.addTab(self.export_tab, "导出")
        self.tabs.addTab(self.settings_tab, "设置")
        self.setCentralWidget(self.tabs)

        status = QStatusBar()
        self.db_label = QLabel("台账: %s" % db_path)
        status.addWidget(self.db_label)
        status.addPermanentWidget(QLabel(DISCLAIMER))
        self.setStatusBar(status)

        self.import_tab.import_finished.connect(self.refresh_all)
        self.settings_tab.db_reopened.connect(self._on_db_reopened)
        self.refresh_all()

    def refresh_all(self) -> None:
        self.ledger_tab.refresh()
        self.findings_tab.refresh()
        self.dashboard_tab.refresh()
        self.export_tab.refresh()
        self.settings_tab.refresh()
        self.db_label.setText("台账: %s" % self.ctx.db_path)

    def _on_db_reopened(self, path: str) -> None:
        self.ctx.reopen(path)
        self.refresh_all()

    def closeEvent(self, event) -> None:
        try:
            self.ctx.ledger.close()
        except Exception:
            pass
        super().closeEvent(event)


def run_app(db_path: str = "ledger.db") -> int:
    """QApplication 主循环；依赖门由 cli._cmd_app 在导入本模块前完成。

    冒烟探针（打包验证通路）：环境变量 INVOICE_LEDGER_GUI_SMOKE=1 时
    窗口显示 1.5s 后自动退出，供无 Python 机器无人值守验证 GUI 可启动。
    """
    import os

    from PySide6.QtCore import QTimer

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("invoice-ledger-checker")
    window = MainWindow(db_path=db_path)
    window.show()
    if os.environ.get("INVOICE_LEDGER_GUI_SMOKE") == "1":
        QTimer.singleShot(1500, app.quit)
    return app.exec_()
