"""数电票 XML 数据电文解析器（FR-02，题目亮点；M2 交付）。

设计契约：plan/04 §2.1；字段映射权威出处 data/samples/TEMPLATE_REFERENCE.md §1
（M1 生成器 synthetic-v1 模板即 v1 映射；官方样例查到后追加第二套映射并标"待核对"）。

实现要点：
- stdlib ElementTree，读 bytes 交给 fromstring（由 XML 声明决定解码）；
  stdlib 默认不解析外部实体；注释节点默认忽略（合成数据的"程序生成"标识
  注释因此天然跳过）；
- 字段映射 FIELD_MAP：根内 localname 路径（"InvoiceHeader/InvoiceNumber"）
  -> InvoiceCard 字段，单次递归遍历收集。命名空间防御：带 ns 的文档按
  localname 降级匹配，整卡降置信度并登记 field_flags（ns 白名单待官方
  规范入库后再收紧）；
- 数值清洗走 base.clean_numeric_text + 严格 Decimal 校验：非法值**丢弃**
  （留空串 + field_flags + 降置信度），绝不猜值；
- 结构级失败（文件不可读/非 XML/主键三要素 invoice_number、invoice_type、
  issue_date 任一缺失）抛 ParserError；其余单字段缺失留空串 + flag
  （防幻觉纪律：缺失 != 造默认值）；
- 证据：每个取到值/被清洗的字段记录 Evidence（location=节点路径，quote=原文）。
"""

import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple

from ..models import Evidence, InvoiceCard, LineItem
from .base import ParserError, clean_numeric_text, is_decimal_text

# 根元素内 localname 路径 -> InvoiceCard 字段（TEMPLATE_REFERENCE §1 v1 映射）
FIELD_MAP = {
    "InvoiceHeader/InvoiceNumber": "invoice_number",
    "InvoiceHeader/InvoiceType": "invoice_type",
    "InvoiceHeader/IssueDate": "issue_date",
    "InvoiceHeader/Buyer/Name": "buyer_name",
    "InvoiceHeader/Buyer/TaxId": "buyer_tax_id",
    "InvoiceHeader/Seller/Name": "seller_name",
    "InvoiceHeader/Seller/TaxId": "seller_tax_id",
    "InvoiceHeader/AmountWithoutTax": "amount",
    "InvoiceHeader/TaxAmount": "tax_amount",
    "InvoiceHeader/TotalWithTax": "total_with_tax",
    "InvoiceHeader/TotalWithTaxCN": "total_with_tax_cn",
    "InvoiceHeader/Remark": "remark",
}
# 数值型标量字段（清洗+Decimal 校验）；其余文本字段原样保留
NUMERIC_FIELDS = frozenset({"amount", "tax_amount", "total_with_tax"})
# 主键三要素（models.REQUIRED_FIELDS 同源）：缺失即结构失败
_REQUIRED_FIELDS = ("invoice_number", "invoice_type", "issue_date")
_ITEM_PATH = "InvoiceHeader/Items/Item"
_CONF_NS_PENALTY = 0.1      # localname 降级匹配
_CONF_DROP_PENALTY = 0.2    # 非法数值被丢弃


def parse(path: str) -> InvoiceCard:
    """解析一个数电票 XML 文件为 InvoiceCard。"""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise ParserError("文件不可读: %s（%s）" % (path, exc)) from exc
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ParserError("XML 结构非法: %s（%s）" % (path, exc)) from exc
    return _card_from_root(root, path)


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _card_from_root(root: ET.Element, path: str) -> InvoiceCard:
    found: Dict[str, Tuple[str, str]] = {}  # field -> (raw text, rel path)
    items_raw: List[Dict[str, str]] = []

    def walk(node: ET.Element, rel: str) -> None:
        field = FIELD_MAP.get(rel)
        if field is not None and field not in found:
            found[field] = (node.text or "", rel)
        if rel == _ITEM_PATH:
            items_raw.append({_localname(str(child.tag)): child.text or ""
                              for child in node})
        for child in node:
            walk(child, rel + "/" + _localname(str(child.tag)) if rel
                 else _localname(str(child.tag)))

    walk(root, "")
    root_name = _localname(str(root.tag))
    has_ns = any("}" in str(el.tag) for el in root.iter())

    confidence = 1.0
    field_flags: List[str] = []
    evidence: List[Evidence] = []
    if has_ns:
        confidence -= _CONF_NS_PENALTY
        field_flags.append("xml#namespace_localname_fallback")

    def locate(rel: str) -> str:
        return "/" + root_name + "/" + rel if rel else "/" + root_name

    card_kwargs: Dict[str, object] = {}
    for field in _REQUIRED_FIELDS:
        raw, rel = found.get(field, ("", ""))
        text = (raw or "").strip()
        if not text:
            raise ParserError("结构失败：%s 缺失，无法构成发票卡（%s）" % (field, path))
        card_kwargs[field] = text
        evidence.append(Evidence(source_file=path, quote=text, location=locate(rel)))

    for field, (raw, rel) in found.items():
        if field in _REQUIRED_FIELDS:
            continue
        text = (raw or "").strip()
        if not text:
            field_flags.append("%s#missing" % field)
            continue
        kept = text
        if field in NUMERIC_FIELDS:
            kept, ok = _clean_numeric(raw)
            if not ok:
                confidence -= _CONF_DROP_PENALTY
                field_flags.append("%s#invalid_number_dropped" % field)
        card_kwargs[field] = kept
        evidence.append(Evidence(source_file=path, quote=text, location=locate(rel)))

    # 可选字段节点整体缺席（如空备注、INJ-FIELD-MISS 抹除）同样登记，不造值
    for _rel, field in FIELD_MAP.items():
        if field in _REQUIRED_FIELDS or field in found:
            continue
        field_flags.append("%s#absent" % field)

    card_kwargs["items"] = _parse_items(root_name, items_raw, path,
                                        field_flags, evidence)
    card_kwargs["confidence"] = max(0.0, confidence)
    card_kwargs["field_flags"] = field_flags
    card_kwargs["evidence"] = evidence
    return InvoiceCard(**card_kwargs)  # type: ignore[arg-type]


def _parse_items(root_name: str, items_raw: List[Dict[str, str]], path: str,
                 field_flags: List[str], evidence: List[Evidence]) -> List[LineItem]:
    rows: List[LineItem] = []
    for idx, cells in enumerate(items_raw, start=1):
        base_loc = "/%s/InvoiceHeader/Items/Item[%d]" % (root_name, idx)
        name = cells.get("Name", "").strip()
        amount, amount_ok = _clean_numeric(cells.get("Amount", ""))
        tax, tax_ok = _clean_numeric(cells.get("TaxAmount", ""))
        rate_raw = cells.get("TaxRate")
        if rate_raw is None:
            rate, rate_ok = "", True   # 仅末行可缺（TEMPLATE_REFERENCE §1）
        else:
            rate, rate_ok = _clean_numeric(rate_raw)
        for cell, ok in (("amount", amount_ok), ("tax_rate", rate_ok),
                         ("tax_amount", tax_ok)):
            if not ok:
                field_flags.append("items[%d].%s#invalid_number_dropped" % (idx, cell))
        for cell, raw in (("Name", cells.get("Name", "")),
                          ("Amount", cells.get("Amount", "")),
                          ("TaxRate", rate_raw or ""),
                          ("TaxAmount", cells.get("TaxAmount", ""))):
            if raw:
                evidence.append(Evidence(source_file=path, quote=raw,
                                         location=base_loc + "/" + cell))
        rows.append(LineItem(name=name, amount=amount, tax_rate=rate, tax_amount=tax))
    return rows


def _clean_numeric(raw: str) -> Tuple[str, bool]:
    cleaned = clean_numeric_text(raw or "")
    if not cleaned or not is_decimal_text(cleaned):
        return "", False
    try:
        Decimal(cleaned)
    except InvalidOperation:
        return "", False
    return cleaned, True
