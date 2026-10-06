"""解析层公共契约（plan/04 §2）。"""

import re
from typing import Callable, Optional

from ..models import InvoiceCard

# 支持的后缀 -> 解析器注册名（OFD 为 P2 加分项）
SUPPORTED_SUFFIXES = (".xml", ".pdf", ".ofd")


class ParserError(Exception):
    """结构级解析失败（区别于字段缺失：字段缺失走空串+field_flags 降级）。"""


ParserFunc = Callable[[str], InvoiceCard]

# 数值清洗（plan/04 §2.1，XML/PDF 解析器共用）：全角->半角、千分位/货币符号剥离。
_FULLWIDTH_TRANS = {
    ord("０") + i: str(i) for i in range(10)
}
_FULLWIDTH_TRANS.update({
    ord("．"): ".", ord("－"): "-", ord("＋"): "+",
    ord("　"): " ", ord("，"): ",",
})
_MONEY_SYMBOLS = ("￥", "¥", "元", "RMB", "CNY")
_NUMERIC_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def clean_numeric_text(text: str) -> str:
    """金额/税率文本清洗：返回可参与 Decimal 校验的半角文本（不改变合法原值）。

    剥离货币符号与千分位分隔符、全角数字/小数点转半角；调用方对返回值做
    Decimal 校验，非法即丢弃该值并降置信度（数值超范围即丢弃纪律）。
    """
    out = (text or "").translate(_FULLWIDTH_TRANS)
    for symbol in _MONEY_SYMBOLS:
        out = out.replace(symbol, "")
    out = out.replace(" ", "").replace(",", "")
    return out.strip()


def is_decimal_text(text: str) -> bool:
    """严格十进制数值判定（拒绝 nan/inf/科学计数法等 Decimal 也接受的形态）。"""
    return bool(_NUMERIC_RE.match(text))


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
