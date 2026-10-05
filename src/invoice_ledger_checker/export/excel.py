"""Excel 台账导出（openpyxl；M5 交付，FR-20）。

设计要点：发票 sheet + 异常清单 sheet + 条件格式标红；openpyxl 经
extras: export 惰性导入。docx 摘要报告为 P2（extras: report）。
"""

from typing import Any, Dict


def export_ledger(db_path: str, out_path: str) -> Dict[str, Any]:
    raise NotImplementedError("Excel 导出属 M5 交付（plan/05 里程碑）；骨架未实现。")
