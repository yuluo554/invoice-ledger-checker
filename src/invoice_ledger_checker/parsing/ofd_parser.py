"""OFD 发票解析器（FR-04，P2 加分项；进度风险首顺延）。

设计要点（plan/04 §2.3）：OFD 本质是 zip 包内 XML 集（GB/T 33190）；
zipfile 打开 -> OFD.xml 定位文档结构 -> 逐页 content XML 抽文本，
字段映射复用 PDF 的 label-slot 逻辑。
"""

from ..models import InvoiceCard
from .base import ParserError


def parse(path: str) -> InvoiceCard:
    """解析一个 OFD 发票文件为 InvoiceCard。P2，M2 尾视进度交付。"""
    raise NotImplementedError("OFD 解析器为 P2 加分项（plan/02 FR-04）；骨架未实现。")
