"""数电票 XML 数据电文解析器（FR-02，题目亮点；M2 交付）。

设计要点（plan/04 §2.1，骨架期先落契约）：
- stdlib ElementTree；读 bytes 按 UTF-8 解码；不解析外部实体；
- 字段映射 FIELD_MAP：XML 节点路径 -> InvoiceCard 字段。M1 生成器模板即
  权威映射；官方样例查到后追加第二套映射（配置切换）并标注"待核对"；
- namespace 处理：{ns}tag 匹配失败降级 localname 匹配并降置信度；
- 数值清洗：千分位/全角/货币符号剥离，清洗后非合法 Decimal 即丢弃该值
  并降置信度（数值超范围即丢弃纪律）；
- 明细行：遍历明细容器节点逐行构造 LineItem；
- 证据：每字段记录节点路径 + 原始文本。
"""

from ..models import InvoiceCard
from .base import ParserError


def parse(path: str) -> InvoiceCard:
    """解析一个数电票 XML 文件为 InvoiceCard。M2 交付。"""
    raise NotImplementedError("数电票 XML 解析器属 M2 交付（plan/05 里程碑）；骨架未实现。")
