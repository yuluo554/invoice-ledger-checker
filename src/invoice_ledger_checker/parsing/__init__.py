"""解析层：各格式解析器 -> InvoiceCard（契约见 plan/04 §2）。"""

from .base import SUPPORTED_SUFFIXES, ParserError, parser_for

__all__ = ["SUPPORTED_SUFFIXES", "ParserError", "parser_for"]
