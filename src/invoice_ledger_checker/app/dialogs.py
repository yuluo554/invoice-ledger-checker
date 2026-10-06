"""GUI 对话框（M5）：发票新增/编辑、发票详情、导入结果摘要。

对话框只做数据录入与展示；入库/更新走 storage.Ledger，检测参数
生效于下一次导入检测（引擎参数单一来源 = context.engine_params）。
"""

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..models import InvoiceCard

INVOICE_TYPES = ["数电普票", "数电专票", "电子普票", "纸质专票", "纸质普票"]


class InvoiceEditDialog(QDialog):
    """新增/编辑发票（FR-08）。编辑态仅联系人字段可改——号码/金额/日期
    属对账链字段，改动破坏检测可追溯性，只读保护。"""

    def __init__(self, parent=None, card: InvoiceCard = None,
                 mode: str = "add") -> None:
        super().__init__(parent)
        self.mode = mode
        self.card = card
        editing = mode == "edit" and card is not None
        self.setWindowTitle("编辑发票" if editing else "新增发票（手工录入）")
        form = QFormLayout(self)

        self.number_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(INVOICE_TYPES)
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYY-MM-DD")
        self.buyer_edit = QLineEdit()
        self.seller_edit = QLineEdit()
        self.total_edit = QLineEdit()
        self.total_edit.setPlaceholderText("价税合计，如 1130.00")
        self.remark_edit = QLineEdit()

        form.addRow("发票号码*", self.number_edit)
        form.addRow("发票类型*", self.type_combo)
        form.addRow("开票日期*", self.date_edit)
        form.addRow("购买方", self.buyer_edit)
        form.addRow("销售方", self.seller_edit)
        form.addRow("价税合计*", self.total_edit)
        form.addRow("备注", self.remark_edit)

        if editing:
            self.number_edit.setText(card.invoice_number)
            self.number_edit.setReadOnly(True)
            idx = self.type_combo.findText(card.invoice_type)
            self.type_combo.setCurrentIndex(max(idx, 0))
            self.type_combo.setEnabled(False)
            self.date_edit.setText(card.issue_date)
            self.date_edit.setReadOnly(True)
            self.buyer_edit.setText(card.buyer_name)
            self.seller_edit.setText(card.seller_name)
            self.total_edit.setText(card.total_with_tax)
            self.total_edit.setReadOnly(True)
            self.remark_edit.setText(card.remark)
            note = QLabel("编辑态仅购买方/销售方/备注可改；金额与号码为对账链字段只读。")
            form.addRow(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _validated_card(self):
        """新增态校验必填 + 金额合法性；非法返回 None（调用方提示）。"""
        number = self.number_edit.text().strip()
        issue_date = self.date_edit.text().strip()
        total = self.total_edit.text().strip()
        if not number or not issue_date or not total:
            return None
        try:
            Decimal(total)
        except InvalidOperation:
            return None
        return InvoiceCard(
            invoice_number=number,
            invoice_type=self.type_combo.currentText(),
            issue_date=issue_date,
            buyer_name=self.buyer_edit.text().strip(),
            seller_name=self.seller_edit.text().strip(),
            total_with_tax=total,
            remark=self.remark_edit.text().strip(),
            batch_id="manual",
        )

    def accept(self) -> None:
        if self.mode == "add" and self._validated_card() is None:
            QMessageBox.warning(
                self, "输入不完整",
                "发票号码/开票日期/价税合计为必填，价税合计须为合法金额。")
            return
        super().accept()

    def get_card(self):
        if self.mode == "edit":
            return None  # 编辑态由调用方读取各字段增量
        return self._validated_card()

    def field_values(self):
        """编辑态读取：buyer/seller/remark 增量。"""
        return {
            "buyer_name": self.buyer_edit.text().strip(),
            "seller_name": self.seller_edit.text().strip(),
            "remark": self.remark_edit.text().strip(),
        }


class InvoiceDetailDialog(QDialog):
    """发票详情（异常清单双击跳转，FR-18）：全字段 + 明细 + 证据原文。"""

    def __init__(self, parent=None, card: InvoiceCard = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("发票详情 %s" % (card.invoice_number if card else ""))
        layout = QVBoxLayout(self)
        if card is None:
            layout.addWidget(QLabel("未找到该发票（可能已被删除）。"))
        else:
            lines = [
                "发票号码: %s" % card.invoice_number,
                "发票类型: %s    开票日期: %s" % (card.invoice_type, card.issue_date),
                "购买方: %s (%s)" % (card.buyer_name, card.buyer_tax_id),
                "销售方: %s (%s)" % (card.seller_name, card.seller_tax_id),
                "金额: %s + 税额 %s = 价税合计 %s" % (
                    card.amount, card.tax_amount, card.total_with_tax),
                "价税合计大写: %s" % card.total_with_tax_cn,
                "批次: %s    置信度: %s    字段标记: %s" % (
                    card.batch_id, card.confidence,
                    "、".join(card.field_flags) or "无"),
                "备注: %s" % card.remark,
            ]
            for item in card.items:
                lines.append("  明细: %s  金额 %s  税率 %s  税额 %s" % (
                    item.name, item.amount, item.tax_rate, item.tax_amount))
            text = QPlainTextEdit("\n".join(lines))
            text.setReadOnly(True)
            layout.addWidget(text)
            evidence_lines = []
            for ev in card.evidence:
                evidence_lines.append("[%s] %s\n    %s" % (
                    ev.source_file, ev.location, ev.quote))
            evidence_box = QPlainTextEdit("\n".join(evidence_lines) or "（无证据记录）")
            evidence_box.setReadOnly(True)
            evidence_box.setPlaceholderText("证据面板")
            layout.addWidget(evidence_box)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class ImportSummaryDialog(QDialog):
    """导入结果摘要（FR-01）：批次统计 + 拒绝清单 + 异常计数。"""

    def __init__(self, parent=None, summary_text: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("导入完成")
        layout = QVBoxLayout(self)
        text = QPlainTextEdit(summary_text)
        text.setReadOnly(True)
        layout.addWidget(text)
        ok = QPushButton("确定")
        ok.clicked.connect(self.accept)
        layout.addWidget(ok)
        self.resize(560, 380)
