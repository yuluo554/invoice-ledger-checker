"""InvoiceCard 发票参数卡：统一中间表示。

契约权威出处：plan/04-模块详设.md §1。字段名/嵌套结构是既定口径，
变更必须先改 plan/04 再改这里，并在 HANDOFF 既定口径登记。

约定：
- 金额一律 Decimal 文本（str），比较校验在应用层用 Decimal 做，杜绝浮点误差；
- 解析不到的字段留空串 + field_flags 登记，不造默认值（防幻觉纪律）；
- invoice_number 是主键，缺失的卡不得入库（from_dict 强校验）。
"""

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List

REQUIRED_FIELDS = ("invoice_number", "invoice_type", "issue_date")


@dataclass
class Evidence:
    """字段证据：来源文件 + 原文摘录（+可选定位），支撑异常判定溯源。"""

    source_file: str          # 相对导入路径（不存绝对路径，防隐私泄露）
    quote: str                # 原文摘录（PDF 文本层片段 / XML 原始文本）
    location: str = ""        # 页码或 XML 节点路径


@dataclass
class LineItem:
    """项目明细行（plan/04 §1）。"""

    name: str                 # 品名/项目名称
    amount: str               # 金额（不含税），Decimal 文本
    tax_rate: str             # 税率，如 "0.13"
    tax_amount: str           # 税额，Decimal 文本


@dataclass
class InvoiceCard:
    invoice_number: str       # 数电票 20 位号码（主键）
    invoice_type: str         # 数电普票/数电专票/电子普票/纸质专票/纸质普票
    issue_date: str           # 开票日期 YYYY-MM-DD（字符串序即时间序）
    buyer_name: str = ""
    buyer_tax_id: str = ""    # 统一社会信用代码（18 位；合成数据为假格式）
    seller_name: str = ""
    seller_tax_id: str = ""
    items: List[LineItem] = field(default_factory=list)
    amount: str = ""          # 合计金额（不含税）
    tax_amount: str = ""      # 合计税额
    total_with_tax: str = ""  # 价税合计
    total_with_tax_cn: str = ""  # 价税合计大写
    remark: str = ""
    batch_id: str = ""        # 导入批次号（入库时填充）
    confidence: float = 1.0   # 整卡置信度；字段级问题进 field_flags
    field_flags: List[str] = field(default_factory=list)  # 如 ["remark#low_conf"]
    evidence: List[Evidence] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """与真值 JSON/基准对账同构的 dict 形态（plan/05 §3）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvoiceCard":
        """从 dict 重建；主键 invoice_number 缺失/为空即拒绝（ValueError）。

        未知键忽略（向前兼容），items/evidence 还原为子对象列表。
        """
        if not data.get("invoice_number"):
            raise ValueError("invoice_number 缺失：无主键的发票卡不得创建/入库")
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        items = [LineItem(**item) for item in filtered.pop("items", [])]
        evidence = [Evidence(**ev) for ev in filtered.pop("evidence", [])]
        return cls(items=items, evidence=evidence, **filtered)
