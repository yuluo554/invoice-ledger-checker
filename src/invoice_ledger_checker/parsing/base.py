"""解析层公共契约（plan/04 §2）。"""

from typing import Callable, Optional

from ..models import InvoiceCard

# 支持的后缀 -> 解析器注册名（OFD 为 P2 加分项）
SUPPORTED_SUFFIXES = (".xml", ".pdf", ".ofd")


class ParserError(Exception):
    """结构级解析失败（区别于字段缺失：字段缺失走空串+field_flags 降级）。"""


ParserFunc = Callable[[str], InvoiceCard]


def parser_for(suffix: str) -> Optional[ParserFunc]:
    """按文件后缀返回解析函数；未支持格式返回 None（调用方记导入日志跳过）。"""
    suffix = suffix.lower()
    if suffix == ".xml":
        from . import xml_parser

        return xml_parser.parse
    if suffix == ".pdf":
        from . import pdf_parser

        return pdf_parser.parse
    if suffix == ".ofd":
        from . import ofd_parser

        return ofd_parser.parse
    return None
