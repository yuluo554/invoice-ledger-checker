"""GUI 六窗口组件（M5，plan/04 §6）。

导入向导 / 台账表格（分页+筛选+增删改查）/ 异常清单（级别着色+证据面板）/
看板（QtCharts 三图）/ 导出对话框 / 设置。所有数据操作只走 storage.Ledger
与 cli 流水线函数（单一事实源，GUI 不另起第二套行为）。
"""

import json
import os
from datetime import date

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QLineSeries,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..cli import _register_batches, _run_check_pipeline, _scan_and_parse
from ..export.excel import export_ledger
from .dialogs import ImportSummaryDialog, InvoiceDetailDialog, InvoiceEditDialog
from .models import LEVEL_LABELS, FindingsTableModel, InvoiceTableModel

PAGE_SIZE = 50  # 台账分页大小（测试可 monkeypatch 验分页）

_LEVEL_ORDER = ("error", "suspicious", "review")


def _count_by_level(findings) -> dict:
    """按级别计数（引擎返回 Finding 对象，与 cli._print_findings 同构）。"""
    counts = {level: 0 for level in _LEVEL_ORDER}
    for finding in findings:
        counts[finding.level] = counts.get(finding.level, 0) + 1
    return counts


class ImportTab(QWidget):
    """导入向导（FR-01）：文件夹选择 -> 批次摘要 + 导入日志（坏文件清单）。"""

    import_finished = Signal()

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("发票文件夹:"))
        self.path_edit = QLineEdit()
        row.addWidget(self.path_edit, stretch=1)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._pick_folder)
        row.addWidget(browse)
        layout.addLayout(row)

        self.import_btn = QPushButton("导入并检测（解析 -> 入库 -> 八规则）")
        self.import_btn.clicked.connect(self._do_import)
        layout.addWidget(self.import_btn)

        layout.addWidget(QLabel("导入日志:"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("选择文件夹后点击导入；日志显示批次统计、"
                                    "拒绝清单与异常计数。")
        layout.addWidget(self.log, stretch=1)

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择发票文件夹")
        if folder:
            self.path_edit.setText(folder)

    def _do_import(self) -> None:
        folder = self.path_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "导入", "请先选择存在的发票文件夹。")
            return
        result = _scan_and_parse(folder)
        if not result["files"]:
            QMessageBox.warning(self, "导入", "文件夹内无可解析的发票文件。")
            return
        _register_batches(result, self.ctx.ledger, source_desc=folder)
        accepted, pk_rejected, findings = _run_check_pipeline(
            result, self.ctx.ledger, {}, date.today().isoformat(),
            engine_params=self.ctx.engine_params)
        counts = _count_by_level(findings)
        lines = [
            "输入: %s（批次=一级子目录名）" % folder,
            "扫描: %d 个文件，成功解析 %d 张卡" % (
                len(result["files"]), len(result["cards"])),
        ]
        for fmt in sorted(result["ok_by_format"]):
            lines.append("  %s 成功 %d" % (fmt, result["ok_by_format"][fmt]))
        for batch_id in sorted(result["batches"]):
            stat = result["batches"][batch_id]
            lines.append("  批次 %s: 成功 %d / 失败 %d / OFD 顺延 %d" % (
                batch_id, stat["ok"], stat["rejected"], stat["deferred"]))
        if result["rejected"]:
            lines.append("拒绝清单: %d 个" % len(result["rejected"]))
            lines.extend("  %s — %s" % (p, r) for p, r in result["rejected"])
        if result["deferred_ofd"]:
            lines.append("OFD 顺延登记: %d 个（P2 加分项未解析）"
                         % len(result["deferred_ofd"]))
        if result["dep_blocked"]:
            lines.append("缺依赖未解析: %d 个（需安装 .[parse] 后重导）"
                         % len(result["dep_blocked"]))
        lines.append("入库: %d 张（主键拒收同号副本 %d 张）"
                     % (accepted, len(pk_rejected)))
        lines.append("八规则检测: 异常 %d 条（%s）" % (
            len(findings),
            " / ".join("%s %d" % (LEVEL_LABELS[level], counts[level])
                       for level in _LEVEL_ORDER)))
        summary_text = "\n".join(lines)
        self.log.setPlainText(summary_text)
        ImportSummaryDialog(self, summary_text).exec_()
        self.import_finished.emit()

    def refresh(self) -> None:
        pass  # 日志保留上次导入记录


class LedgerTab(QWidget):
    """台账表格（FR-07/08）：多维筛选 + 分页 + 增删改查。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.page = 1
        self.total = 0
        layout = QVBoxLayout(self)

        filters = QGridLayout()
        filters.addWidget(QLabel("月份"), 0, 0)
        self.month_combo = QComboBox()
        filters.addWidget(self.month_combo, 0, 1)
        filters.addWidget(QLabel("类型"), 0, 2)
        self.type_combo = QComboBox()
        filters.addWidget(self.type_combo, 0, 3)
        filters.addWidget(QLabel("供应商"), 0, 4)
        self.seller_edit = QLineEdit()
        self.seller_edit.setPlaceholderText("名称/税号包含…")
        filters.addWidget(self.seller_edit, 0, 5)
        filters.addWidget(QLabel("价税合计区间"), 0, 6)
        self.min_edit = QLineEdit()
        self.min_edit.setPlaceholderText("最小")
        self.max_edit = QLineEdit()
        self.max_edit.setPlaceholderText("最大")
        filters.addWidget(self.min_edit, 0, 7)
        filters.addWidget(self.max_edit, 0, 8)
        query_btn = QPushButton("查询")
        query_btn.clicked.connect(self._on_query)
        filters.addWidget(query_btn, 0, 9)
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._on_reset)
        filters.addWidget(reset_btn, 0, 10)
        layout.addLayout(filters)

        self.model = InvoiceTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

        pager = QHBoxLayout()
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self._go_prev)
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self._go_next)
        self.page_label = QLabel("第 1 / 1 页（共 0 条）")
        pager.addWidget(self.prev_btn)
        pager.addWidget(self.page_label)
        pager.addWidget(self.next_btn)
        pager.addStretch(1)

        add_btn = QPushButton("新增")
        add_btn.clicked.connect(self._add_invoice)
        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self._edit_invoice)
        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self._delete_invoice)
        detail_btn = QPushButton("详情")
        detail_btn.clicked.connect(self._show_detail)
        for btn in (add_btn, edit_btn, delete_btn, detail_btn):
            pager.addWidget(btn)
        layout.addLayout(pager)

    # ---- 查询与分页 ----

    def _current_filters(self):
        month = self.month_combo.currentText()
        invoice_type = self.type_combo.currentText()
        return {
            "month": month if month != "全部" else None,
            "invoice_type": invoice_type if invoice_type != "全部" else None,
            "seller_like": self.seller_edit.text().strip() or None,
            "amount_min": self.min_edit.text().strip() or None,
            "amount_max": self.max_edit.text().strip() or None,
        }

    def _load_page(self) -> None:
        rows, self.total = self.ctx.ledger.query_invoices(
            page=self.page, page_size=PAGE_SIZE, **self._current_filters())
        self.model.set_rows(rows)
        pages = max(1, -(-self.total // PAGE_SIZE))
        self.page = min(self.page, pages)
        self.page_label.setText("第 %d / %d 页（共 %d 条）"
                                % (self.page, pages, self.total))
        self.prev_btn.setEnabled(self.page > 1)
        self.next_btn.setEnabled(self.page < pages)

    def _on_query(self) -> None:
        self.page = 1
        self._load_page()

    def _on_reset(self) -> None:
        self.seller_edit.clear()
        self.min_edit.clear()
        self.max_edit.clear()
        self.month_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.page = 1
        self._load_page()

    def _go_prev(self) -> None:
        if self.page > 1:
            self.page -= 1
            self._load_page()

    def _go_next(self) -> None:
        pages = max(1, -(-self.total // PAGE_SIZE))
        if self.page < pages:
            self.page += 1
            self._load_page()

    def _selected_number(self):
        index = self.table.currentIndex()
        if not index.isValid():
            QMessageBox.information(self, "台账", "请先在表格中选择一行。")
            return None
        row = self.model.row_at(index.row())
        return row["invoice_number"] if row else None

    # ---- 增删改查（FR-08） ----

    def _add_invoice(self) -> None:
        dialog = InvoiceEditDialog(self, mode="add")
        if dialog.exec_() != InvoiceEditDialog.Accepted:
            return
        card = dialog.get_card()
        if card is None:
            return
        self.ctx.ledger.create_batch("manual", source_desc="GUI 手工录入")
        if not self.ctx.ledger.add_invoice(card, "manual"):
            QMessageBox.warning(self, "新增", "同号发票已存在（重复录入本身"
                                "是 R-DUP-01 异常信号，不覆盖）。")
        self.refresh()

    def _edit_invoice(self) -> None:
        number = self._selected_number()
        if not number:
            return
        card = self.ctx.ledger.get_invoice(number)
        if card is None:
            return
        dialog = InvoiceEditDialog(self, card=card, mode="edit")
        if dialog.exec_() != InvoiceEditDialog.Accepted:
            return
        self.ctx.ledger.update_invoice_fields(number, **dialog.field_values())
        self.refresh()

    def _delete_invoice(self) -> None:
        number = self._selected_number()
        if not number:
            return
        answer = QMessageBox.question(
            self, "删除确认", "确定删除发票 %s 吗？该操作不可撤销。" % number)
        if answer != QMessageBox.Yes:
            return
        self.ctx.ledger.delete_invoice(number)
        self.refresh()

    def _show_detail(self) -> None:
        number = self._selected_number()
        if not number:
            return
        InvoiceDetailDialog(self, card=self.ctx.ledger.get_invoice(number)).exec_()

    def refresh(self) -> None:
        ledger = self.ctx.ledger
        months = ["全部"] + ledger.distinct_months()
        types = ["全部"] + ledger.distinct_invoice_types()
        for combo, values in ((self.month_combo, months),
                              (self.type_combo, types)):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(values)
            if current in values:
                combo.setCurrentText(current)
            combo.blockSignals(False)
        self._load_page()


class FindingsTab(QWidget):
    """异常清单（FR-18）：按级别分组着色 + 证据面板 + 复核状态动作。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("级别"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["全部"] + [LEVEL_LABELS[l] for l in _LEVEL_ORDER])
        self.level_combo.currentIndexChanged.connect(lambda _: self.refresh())
        row.addWidget(self.level_combo)
        row.addStretch(1)
        confirm_btn = QPushButton("标记已确认")
        confirm_btn.clicked.connect(lambda: self._set_status("confirmed"))
        dismiss_btn = QPushButton("标记忽略")
        dismiss_btn.clicked.connect(lambda: self._set_status("dismissed"))
        reopen_btn = QPushButton("重置待处理")
        reopen_btn.clicked.connect(lambda: self._set_status("open"))
        for btn in (confirm_btn, dismiss_btn, reopen_btn):
            row.addWidget(btn)
        layout.addLayout(row)

        self.model = FindingsTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_detail)
        self.table.selectionModel().currentRowChanged.connect(
            lambda *_: self._show_evidence())
        layout.addWidget(self.table, stretch=2)

        layout.addWidget(QLabel("证据面板（选中异常显示；原文摘录可溯源）:"))
        self.evidence = QPlainTextEdit()
        self.evidence.setReadOnly(True)
        layout.addWidget(self.evidence, stretch=1)

    def _set_status(self, status: str) -> None:
        index = self.table.currentIndex()
        if not index.isValid():
            QMessageBox.information(self, "异常清单", "请先选择一条异常记录。")
            return
        finding = self.model.finding_at(index.row())
        if finding:
            self.ctx.ledger.set_finding_status(finding["finding_id"], status)
            self.refresh()

    def _show_evidence(self) -> None:
        index = self.table.currentIndex()
        if not index.isValid():
            return
        finding = self.model.finding_at(index.row())
        if finding is None:
            return
        text = "说明: %s\n关联发票: %s\n\n证据:\n%s" % (
            finding["message"],
            "、".join(finding["invoice_numbers"]) or "（无）",
            json.dumps(finding.get("evidence", {}), ensure_ascii=False, indent=2),
        )
        self.evidence.setPlainText(text)

    def _open_detail(self, index) -> None:
        finding = self.model.finding_at(index.row())
        if not finding or not finding["invoice_numbers"]:
            return
        card = self.ctx.ledger.get_invoice(finding["invoice_numbers"][0])
        InvoiceDetailDialog(self, card=card).exec_()

    def refresh(self) -> None:
        findings = self.ctx.ledger.list_findings()
        index = self.level_combo.currentIndex()
        if index > 0:
            level = _LEVEL_ORDER[index - 1]
            findings = [f for f in findings if f["level"] == level]
        self.model.set_rows(findings)


class DashboardTab(QWidget):
    """看板（FR-09）：QtCharts 月度趋势折线 / 供应商 Top-N 柱形 / 类型分布饼图。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        layout = QHBoxLayout(self)
        self.line_view = QChartView()
        self.bar_view = QChartView()
        self.pie_view = QChartView()
        for view in (self.line_view, self.bar_view, self.pie_view):
            view.setRenderHint(QPainter.Antialiasing)
            layout.addWidget(view)

    def _replace_chart(self, view, chart: QChart) -> None:
        old = view.chart()
        view.setChart(chart)
        if old is not None:
            old.deleteLater()

    def _line_chart(self, stats) -> QChart:
        chart = QChart()
        chart.setTitle("月度开票趋势")
        if not stats:
            chart.setTitle("月度开票趋势（无数据）")
            return chart
        count_series = QLineSeries()
        count_series.setName("发票张数")
        amount_series = QLineSeries()
        amount_series.setName("月度价税合计")
        categories = QBarCategoryAxis()
        for i, row in enumerate(stats):
            categories.append(row["month"])
            count_series.append(i, row["count"])
            amount_series.append(i, row["total"])
        chart.addSeries(count_series)
        chart.addSeries(amount_series)
        chart.addAxis(categories, Qt.AlignBottom)
        axis_count = QValueAxis()
        axis_count.setTitleText("张数")
        axis_count.setLabelFormat("%d")
        chart.addAxis(axis_count, Qt.AlignLeft)
        axis_amount = QValueAxis()
        axis_amount.setTitleText("价税合计（元）")
        chart.addAxis(axis_amount, Qt.AlignRight)
        for series, axis in ((count_series, axis_count),
                             (amount_series, axis_amount)):
            series.attachAxis(categories)
            series.attachAxis(axis)
        return chart

    def _bar_chart(self, sellers) -> QChart:
        chart = QChart()
        chart.setTitle("供应商 Top-%d（按张数）" % len(sellers))
        if not sellers:
            chart.setTitle("供应商 Top-N（无数据）")
            return chart
        series = QBarSeries()
        barset = QBarSet("发票张数")
        names = []
        for row in sellers:
            name = row["seller_name"] or row["seller_tax_id"] or "(未知)"
            names.append(name[:10] + ("…" if len(name) > 10 else ""))
            barset.append(row["count"])
        series.append(barset)
        chart.addSeries(series)
        axis_x = QBarCategoryAxis()
        axis_x.append(names)
        axis_y = QValueAxis()
        axis_y.setLabelFormat("%d")
        chart.addAxis(axis_x, Qt.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        chart.legend().show()
        return chart

    def _pie_chart(self, distribution) -> QChart:
        chart = QChart()
        chart.setTitle("发票类型分布")
        if not distribution:
            chart.setTitle("发票类型分布（无数据）")
            return chart
        series = QPieSeries()
        for row in distribution:
            series.append("%s (%d)" % (row["invoice_type"], row["count"]),
                          row["count"])
        chart.addSeries(series)
        chart.legend().show()
        return chart

    def refresh(self) -> None:
        ledger = self.ctx.ledger
        self._replace_chart(self.line_view, self._line_chart(ledger.monthly_stats()))
        self._replace_chart(self.bar_view, self._bar_chart(ledger.top_sellers(10)))
        self._replace_chart(self.pie_view, self._pie_chart(ledger.type_distribution()))


class ExportTab(QWidget):
    """导出（FR-20）：Excel 导出对话框（进度条）。"""

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "将当前台账导出为 Excel（发票台账 + 异常清单双 sheet，"
            "异常按级别条件格式着色）。"))

        row = QHBoxLayout()
        row.addWidget(QLabel("输出文件:"))
        self.out_edit = QLineEdit()
        row.addWidget(self.out_edit, stretch=1)
        browse = QPushButton("选择…")
        browse.clicked.connect(self._pick_out)
        row.addWidget(browse)
        layout.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.export_btn = QPushButton("导出 Excel")
        self.export_btn.clicked.connect(self._do_export)
        layout.addWidget(self.export_btn)
        self.result_label = QLabel("")
        layout.addWidget(self.result_label)
        layout.addStretch(1)
        self.refresh()

    def _default_out(self) -> str:
        base = os.path.splitext(self.ctx.db_path)[0] or "ledger"
        return base + ".xlsx"

    def _pick_out(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择导出位置", self._default_out(), "Excel 工作簿 (*.xlsx)")
        if path:
            self.out_edit.setText(path)

    def _do_export(self) -> None:
        out_path = self.out_edit.text().strip() or self._default_out()
        if not os.path.isfile(self.ctx.db_path):
            QMessageBox.warning(self, "导出", "台账数据库不存在: %s" % self.ctx.db_path)
            return
        self.progress.setRange(0, 0)  # busy 指示
        try:
            summary = export_ledger(self.ctx.db_path, out_path)
        except Exception as exc:  # 缺依赖/IO 错误统一呈现，不闪退
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.result_label.setText(
            "已导出 %d 张发票、%d 条异常 -> %s"
            % (summary["invoice_count"], summary["finding_count"], out_path))

    def refresh(self) -> None:
        self.out_edit.setPlaceholderText(self._default_out())


class SettingsTab(QWidget):
    """设置（FR-19）：数据库路径 + 检测参数（默认值 = 规则模块 DEFAULT_*）。"""

    db_reopened = Signal(str)

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("数据库路径（台账 SQLite 文件）"))
        row = QHBoxLayout()
        self.db_edit = QLineEdit(ctx.db_path)
        row.addWidget(self.db_edit, stretch=1)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._pick_db)
        row.addWidget(browse)
        open_btn = QPushButton("打开/新建")
        open_btn.clicked.connect(self._reopen_db)
        row.addWidget(open_btn)
        layout.addLayout(row)

        layout.addWidget(QLabel("检测参数（应用后对下一次导入检测生效；"
                                "默认值 = 规则模块常量）"))
        form = QFormLayout()
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setDecimals(2)
        self.tolerance_spin.setRange(0.0, 10.0)
        self.tolerance_spin.setSingleStep(0.01)
        form.addRow("价税合计容差 arith_tolerance", self.tolerance_spin)
        self.dup_tol_spin = QDoubleSpinBox()
        self.dup_tol_spin.setDecimals(2)
        self.dup_tol_spin.setRange(0.0, 10000.0)
        form.addRow("模糊重复金额容差 dup_amount_tol", self.dup_tol_spin)
        self.dup_window_spin = QSpinBox()
        self.dup_window_spin.setRange(0, 365)
        form.addRow("模糊重复日期窗口 dup_date_window_days", self.dup_window_spin)
        self.seq_suffix_spin = QSpinBox()
        self.seq_suffix_spin.setRange(2, 20)
        form.addRow("连号后缀位数 seq_suffix_len", self.seq_suffix_spin)
        self.seq_min_spin = QSpinBox()
        self.seq_min_spin.setRange(2, 20)
        form.addRow("连号最小张数 seq_min_len", self.seq_min_spin)
        self.seq_window_spin = QSpinBox()
        self.seq_window_spin.setRange(1, 365)
        form.addRow("连号日期窗口 seq_date_window_days", self.seq_window_spin)
        self.n_period_spin = QSpinBox()
        self.n_period_spin.setRange(1, 36)
        form.addRow("跨期期数阈值 time_n_period", self.n_period_spin)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("应用参数")
        apply_btn.clicked.connect(self._apply_params)
        default_btn = QPushButton("恢复默认")
        default_btn.clicked.connect(self._reset_params)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(default_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        self._load_params()

    def _pick_db(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择台账数据库", "", "SQLite 数据库 (*.db);;所有文件 (*)")
        if path:
            self.db_edit.setText(path)

    def _reopen_db(self) -> None:
        path = self.db_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "设置", "数据库路径不能为空。")
            return
        self.db_reopened.emit(path)

    def _load_params(self) -> None:
        params = self.ctx.engine_params
        self.tolerance_spin.setValue(float(params["arith_tolerance"]))
        self.dup_tol_spin.setValue(float(params["dup_amount_tol"]))
        self.dup_window_spin.setValue(int(params["dup_date_window_days"]))
        self.seq_suffix_spin.setValue(int(params["seq_suffix_len"]))
        self.seq_min_spin.setValue(int(params["seq_min_len"]))
        self.seq_window_spin.setValue(int(params["seq_date_window_days"]))
        self.n_period_spin.setValue(int(params["time_n_period"]))

    def _apply_params(self) -> None:
        self.ctx.engine_params.update({
            "arith_tolerance": "%.2f" % self.tolerance_spin.value(),
            "dup_amount_tol": "%.2f" % self.dup_tol_spin.value(),
            "dup_date_window_days": self.dup_window_spin.value(),
            "seq_suffix_len": self.seq_suffix_spin.value(),
            "seq_min_len": self.seq_min_spin.value(),
            "seq_date_window_days": self.seq_window_spin.value(),
            "time_n_period": self.n_period_spin.value(),
        })
        QMessageBox.information(
            self, "设置", "检测参数已应用（对下一次导入检测生效）。")

    def _reset_params(self) -> None:
        from .main import DEFAULT_ENGINE_PARAMS

        self.ctx.engine_params = dict(DEFAULT_ENGINE_PARAMS)
        self._load_params()

    def refresh(self) -> None:
        self.db_edit.setText(self.ctx.db_path)
