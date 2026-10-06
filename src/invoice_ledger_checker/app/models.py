"""GUI 表格模型（M5）：台账/异常清单两个 QAbstractTableModel。

只做数据呈现（排序/着色/格式化），业务查询一律走 storage.Ledger——
GUI 不另起第二套行为（与"CLI 单一事实源"同纪律，plan/04 §6）。
"""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

# 三级判定着色（语义同 CLI：error=确认异常 / suspicious=疑似 / review=待人工确认）
LEVEL_FOREGROUND = {
    "error": QColor("#C00000"),
    "suspicious": QColor("#9C6500"),
    "review": QColor("#1F4E79"),
}
LEVEL_LABELS = {"error": "确认异常", "suspicious": "疑似", "review": "待人工确认"}
LEVEL_ORDER = ("error", "suspicious", "review")
STATUS_LABELS = {"open": "待处理", "confirmed": "已确认", "dismissed": "已忽略"}


class InvoiceTableModel(QAbstractTableModel):
    """台账表格（分页查询结果集，一次一页）。"""

    HEADERS = ["发票号码", "类型", "开票日期", "购买方", "销售方",
               "价税合计", "批次"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows = []

    def set_rows(self, rows) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def row_at(self, row: int):
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = ("invoice_number", "invoice_type", "issue_date", "buyer_name",
               "seller_name", "total_with_tax", "batch_id")[index.column()]
        value = row.get(key, "")
        if role == Qt.DisplayRole:
            return str(value)
        if role == Qt.TextAlignmentRole and index.column() == 5:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None


class FindingsTableModel(QAbstractTableModel):
    """异常清单：按级别排序分组着色（error -> suspicious -> review）。"""

    HEADERS = ["级别", "规则ID", "关联发票号码", "说明", "状态", "检出时间"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows = []

    def set_rows(self, findings) -> None:
        def sort_key(f):
            numbers = ",".join(f.get("invoice_numbers", []))
            return (LEVEL_ORDER.index(f.get("level", "review")),
                    f.get("rule_id", ""), numbers)

        self.beginResetModel()
        self._rows = sorted(list(findings), key=sort_key)
        self.endResetModel()

    def finding_at(self, row: int):
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        finding = self._rows[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return LEVEL_LABELS.get(finding.get("level"),
                                        finding.get("level", ""))
            if index.column() == 2:
                return "、".join(finding.get("invoice_numbers", []))
            if index.column() == 4:
                return STATUS_LABELS.get(finding.get("status", "open"),
                                         finding.get("status", "open"))
            key = ("", "rule_id", "", "message", "", "created_at")[index.column()]
            return str(finding.get(key, ""))
        if role == Qt.ForegroundRole and index.column() == 0:
            return LEVEL_FOREGROUND.get(finding.get("level"))
        return None
