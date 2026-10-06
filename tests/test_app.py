"""桌面 GUI 测试（M5）：offscreen 常驻 + 模态对话框全部屏蔽。

纪律（plan/03 §4 + 系列实录）：
- QT_QPA_PLATFORM=offscreen 必须在首次导入 PySide6 之前设置（模块顶部）；
- PySide6 缺失时模块级 importorskip 显式跳过（计数上报，收集数不变）；
- 消息框/文件对话框在触发路径上一律 monkeypatch，绝不弹真模态。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("PySide6.QtCharts")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from invoice_ledger_checker.app import tabs as app_tabs  # noqa: E402
from invoice_ledger_checker.app.dialogs import (  # noqa: E402
    ImportSummaryDialog,
    InvoiceDetailDialog,
    InvoiceEditDialog,
    QMessageBox,
)
from invoice_ledger_checker.app.main import (  # noqa: E402
    DEFAULT_ENGINE_PARAMS,
    MainWindow,
)
from invoice_ledger_checker.generator import generate  # noqa: E402
from invoice_ledger_checker.models import InvoiceCard, LineItem  # noqa: E402
from invoice_ledger_checker.storage import Ledger  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def seeded(tmp_path):
    """三张票（跨月/跨供应商/跨类型）+ 三级 finding 各一条。"""
    ledger = Ledger(str(tmp_path / "ledger.db"))
    ledger.create_batch("b1", source_desc="测试", file_count=3)
    cards = [
        InvoiceCard(
            invoice_number="25910000000000123456", invoice_type="数电普票",
            issue_date="2026-01-05", buyer_name="星辰科技", seller_name="云图商贸",
            seller_tax_id="91330100DEMOFAKE01",
            items=[LineItem(name="会议服务费", amount="1000.00",
                            tax_rate="0.13", tax_amount="130.00")],
            amount="1000.00", tax_amount="130.00", total_with_tax="1130.00",
        ),
        InvoiceCard(
            invoice_number="25910000000000123457", invoice_type="数电专票",
            issue_date="2026-02-10", buyer_name="星辰科技", seller_name="云图商贸",
            seller_tax_id="91330100DEMOFAKE01",
            items=[LineItem(name="咨询费", amount="2000.00",
                            tax_rate="0.13", tax_amount="260.00")],
            amount="2000.00", tax_amount="260.00", total_with_tax="2260.00",
        ),
        InvoiceCard(
            invoice_number="25910000000000123458", invoice_type="电子普票",
            issue_date="2026-02-20", buyer_name="云图商贸", seller_name="星河广告",
            seller_tax_id="91330100DEMOFAKE02",
            amount="500.00", tax_amount="0.00", total_with_tax="500.00",
        ),
    ]
    for card in cards:
        assert ledger.add_invoice(card, "b1")
    for level, rule, numbers in [
        ("error", "R-ARITH-01", ["25910000000000123456"]),
        ("suspicious", "R-DUP-03", ["25910000000000123457"]),
        ("review", "R-TIME-02", ["25910000000000123458"]),
    ]:
        ledger.add_finding({
            "finding_id": "%s:%s" % (rule, "|".join(numbers)),
            "rule_id": rule,
            "level": level,
            "invoice_numbers": numbers,
            "message": "测试 %s 事实" % level,
            "evidence": {"quote": "价税合计（大写）壹仟壹佰叁拾元整"},
        }, batch_id="b1")
    window = MainWindow(str(tmp_path / "ledger.db"))
    yield window
    window.close()
    ledger.close()


def test_window_six_tabs_and_persistent_disclaimer(qapp, seeded):
    window = seeded
    assert window.tabs.count() == 6
    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert titles == ["导入", "台账", "异常清单", "看板", "导出", "设置"]
    assert "台账:" in window.db_label.text()
    status_texts = [w.text() for w in window.statusBar().findChildren(type(window.db_label))]
    assert any("免责声明" in t for t in status_texts)
    assert any("不构成审计意见" in t for t in status_texts)


def test_ledger_tab_rows_filter_and_pagination(qapp, seeded, monkeypatch):
    window = seeded
    tab = window.ledger_tab
    assert tab.model.rowCount() == 3

    monkeypatch.setattr(app_tabs, "PAGE_SIZE", 2)
    tab.page = 1
    tab._load_page()
    assert tab.model.rowCount() == 2
    assert tab.total == 3
    assert tab.next_btn.isEnabled()
    tab._go_next()
    assert tab.model.rowCount() == 1
    assert not tab.next_btn.isEnabled()

    tab._on_reset()
    tab.month_combo.setCurrentText("2026-01")
    tab._on_query()
    assert tab.model.rowCount() == 1
    assert tab.model.row_at(0)["invoice_number"] == "25910000000000123456"

    tab._on_reset()
    tab.type_combo.setCurrentText("电子普票")
    tab._on_query()
    assert tab.model.rowCount() == 1

    tab._on_reset()
    tab.seller_edit.setText("云图")
    tab._on_query()
    assert tab.model.rowCount() == 2

    tab._on_reset()
    tab.min_edit.setText("2000")
    tab._on_query()
    assert tab.model.rowCount() == 1
    assert Decimal(tab.model.row_at(0)["total_with_tax"]) >= Decimal("2000")


def test_ledger_tab_crud(qapp, seeded, monkeypatch):
    window = seeded
    tab = window.ledger_tab

    # 新增：对话框字段由 fake exec_ 填写（不弹模态）
    def fake_add_exec(self):
        self.number_edit.setText("25910000000000999999")
        self.date_edit.setText("2026-03-01")
        self.buyer_edit.setText("测试买方")
        self.seller_edit.setText("测试卖方")
        self.total_edit.setText("100.00")
        return QDialog.Accepted

    monkeypatch.setattr(InvoiceEditDialog, "exec_", fake_add_exec)
    tab._add_invoice()
    assert window.ctx.ledger.get_invoice("25910000000000999999") is not None

    # 编辑：联系人字段增量（号码/金额只读保护）
    def fake_edit_exec(self):
        self.buyer_edit.setText("改名买方")
        return QDialog.Accepted

    monkeypatch.setattr(InvoiceEditDialog, "exec_", fake_edit_exec)
    tab._on_reset()
    for row in range(tab.model.rowCount()):
        if tab.model.row_at(row)["invoice_number"] == "25910000000000123456":
            tab.table.selectRow(row)
            break
    tab._edit_invoice()
    assert window.ctx.ledger.get_invoice(
        "25910000000000123456").buyer_name == "改名买方"

    # 删除：确认框 monkeypatch 为 Yes
    monkeypatch.setattr(
        app_tabs.QMessageBox, "question",
        staticmethod(lambda *a, **k: app_tabs.QMessageBox.Yes))
    tab._on_reset()
    tab.table.selectRow(0)
    target = tab.model.row_at(tab.table.currentIndex().row())["invoice_number"]
    tab._delete_invoice()
    assert window.ctx.ledger.get_invoice(target) is None


def test_findings_tab_evidence_panel_and_status(qapp, seeded, monkeypatch):
    window = seeded
    tab = window.findings_tab
    assert tab.model.rowCount() == 3  # 按 error -> suspicious -> review 排序
    assert tab.model.finding_at(0)["level"] == "error"

    tab.table.selectRow(0)
    assert "证据" in tab.evidence.toPlainText()
    assert "价税合计（大写）" in tab.evidence.toPlainText()

    # 级别筛选
    tab.level_combo.setCurrentIndex(1)  # 确认异常
    assert tab.model.rowCount() == 1
    tab.level_combo.setCurrentIndex(0)
    assert tab.model.rowCount() == 3

    # 复核状态动作落库
    tab.table.selectRow(0)
    target = tab.model.finding_at(0)["finding_id"]
    tab._set_status("confirmed")
    statuses = {f["finding_id"]: f["status"]
                for f in window.ctx.ledger.list_findings()}
    assert statuses[target] == "confirmed"

    # 双击 -> 详情对话框（exec_ 屏蔽）
    monkeypatch.setattr(InvoiceDetailDialog, "exec_",
                        lambda self: QDialog.Accepted)
    tab._open_detail(tab.model.index(0, 0))


def test_dashboard_three_charts_with_series(qapp, seeded):
    window = seeded
    tab = window.dashboard_tab
    line = tab.line_view.chart()
    assert line.title() == "月度开票趋势"
    assert len(line.series()) == 2  # 张数 + 金额双折线
    bar = tab.bar_view.chart()
    assert len(bar.series()) == 1
    assert bar.series()[0].barSets()[0].count() == 2  # 两个供应商
    pie = tab.pie_view.chart()
    assert pie.series()[0].count() == 3  # 三种类型


def test_export_tab_writes_xlsx(qapp, seeded):
    window = seeded
    tab = window.export_tab
    out = window.ctx.db_path.replace(".db", "_export.xlsx")
    tab.out_edit.setText(out)
    tab._do_export()
    assert os.path.isfile(out)
    assert "已导出 3 张发票、3 条异常" in tab.result_label.text()


def test_import_tab_full_pipeline(qapp, seeded, tmp_path, monkeypatch):
    window = seeded
    tab = window.import_tab
    data_dir = tmp_path / "dataset"
    generate(str(data_dir), seed=7, n=6, formats=["xml"])

    monkeypatch.setattr(ImportSummaryDialog, "exec_",
                        lambda self: QDialog.Accepted)
    tab.path_edit.setText(str(tmp_path / "dataset" / "invoices"))
    tab._do_import()
    assert "成功解析 6 张卡" in tab.log.toPlainText()
    assert "八规则检测" in tab.log.toPlainText()
    assert window.ctx.ledger.count_invoices() >= 1
    # 导入完成后全窗口刷新（台账页可见新数据）
    assert window.ledger_tab.model.rowCount() >= 1


def test_import_tab_rejects_missing_folder(qapp, seeded, monkeypatch):
    window = seeded
    tab = window.import_tab
    warned = []
    monkeypatch.setattr(
        app_tabs.QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.append(a) or 0))
    tab.path_edit.setText("definitely/not/a/dir")
    tab._do_import()
    assert warned  # 弹了提示且未崩溃


def test_settings_params_apply_and_reset(qapp, seeded, monkeypatch):
    window = seeded
    tab = window.settings_tab
    info = []
    monkeypatch.setattr(
        app_tabs.QMessageBox, "information",
        staticmethod(lambda *a, **k: info.append(a) or 0))
    tab.tolerance_spin.setValue(0.05)
    tab._apply_params()
    assert info, "应用参数应有确认提示"
    assert window.ctx.engine_params["arith_tolerance"] == "0.05"
    tab._reset_params()
    assert window.ctx.engine_params == DEFAULT_ENGINE_PARAMS

    # 重开数据库信号贯通
    new_db = window.ctx.db_path.replace(".db", "_new.db")
    tab.db_edit.setText(new_db)
    tab._reopen_db()
    assert window.ctx.db_path == new_db
    assert window.db_label.text().endswith(new_db)


def test_invoice_edit_dialog_validation(qapp, monkeypatch):
    """新增对话框必填/金额校验：非法输入弹提示不关闭，合法输入产出卡。"""
    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.append(a) or 0))
    dialog = InvoiceEditDialog(mode="add")
    dialog.accept()  # 必填缺失
    assert warned, "非法输入必须弹提示且不关闭"
    assert not dialog.result() == QDialog.Accepted

    dialog.number_edit.setText("25910000000000888888")
    dialog.date_edit.setText("2026-04-01")
    dialog.total_edit.setText("113.00")
    dialog.accept()
    card = dialog.get_card()
    assert card is not None
    assert card.invoice_number == "25910000000000888888"
    Decimal(card.total_with_tax)
