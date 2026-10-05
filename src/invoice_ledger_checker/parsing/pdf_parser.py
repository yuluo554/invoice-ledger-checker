"""版式 PDF 文本层解析器（FR-03；M2 交付）。

设计要点（plan/04 §2.2，骨架期先落契约）：
- pdfplumber extract_words() 词级 + 坐标；不依赖字符序；
- label-slot：标签词典（"发票号码"/"开票日期"/"价税合计"...）→ 同 y 轴带内
  向右取最近词；多行值按 y/x 邻近聚类合并；大写金额区整行截取；
- 已知陷阱：版式导出伪空格（匹配前剥离全部空白比对）、标签跨行变体；
- 数值区按 x 坐标列聚类归并明细；失败降级"待人工确认"，不猜值；
- 证据：location=页码+词坐标区间，quote=文本层原文。
"""

from ..models import InvoiceCard
from .base import ParserError


def parse(path: str) -> InvoiceCard:
    """解析一个版式发票 PDF（文本层）为 InvoiceCard。M2 交付。"""
    raise NotImplementedError("PDF 文本层解析器属 M2 交付（plan/05 里程碑）；骨架未实现。")
