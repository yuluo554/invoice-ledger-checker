"""版式 PDF 文本层解析器（FR-03；M2 交付）。

设计契约：plan/04 §2.2；版式与标签全集权威出处
data/samples/TEMPLATE_REFERENCE.md §2（M1 生成器版式即 v1 映射）。

实现要点（M2 实测固化，对账 data/invoices 全量 22 份 PDF）：
- pdfplumber extract_words() 词级+坐标，按 top 分行（容差 2pt），不依赖字符序；
- label-slot：标签词典（含全角冒号）在同一行内向右取值——**右边界是同一行
  内下一个标签的 x0**（双栏版式：发票号码行的右侧还有开票日期标签，必须截断）；
- 大写金额：生成器把 `价税合计（大写）：` 与金额画成相邻字符串，值起点与
  标签尾重叠 → pdfplumber 常合并为一个词，取词内冒号后文本；标签/值分词的
  变体走同一入口兼容；
- `（小写）￥X` 为一个词：剥前缀+货币符号后过数值清洗；
- `合计：` 值形如 `51097.17（税额 4743.68）`（空格致分词），正则拆两侧数值；
- 明细表：表头行 `项目名称/金额/税率/税额` 的 x0 即列锚点，表头与合计行之间
  的行按 x0 最近列归并成 LineItem（缺税率单元格为合法空）；
- 数值清洗走 base.clean_numeric_text + 严格 Decimal 校验，非法丢弃+降置信度；
- 失败语义：无文本层/识别不到发票号码、票种标题、开票日期任一要素 →
  ParserError；单字段缺失 → 空串+field_flags（不猜值）；
- 证据：location=页码+y 坐标，quote=文本层原文。
"""

from typing import Any, Dict, List, Optional, Tuple

from ..models import Evidence, InvoiceCard, LineItem
from .base import ParserError, clean_numeric_text, is_decimal_text

# 版式标签 -> InvoiceCard 字段（TEMPLATE_REFERENCE §2 标签全集，含全角冒号）
LABEL_FIELDS = {
    "发票号码：": "invoice_number",
    "开票日期：": "issue_date",
    "购买方名称：": "buyer_name",
    "购买方税号：": "buyer_tax_id",
    "销售方名称：": "seller_name",
    "销售方税号：": "seller_tax_id",
    "备注：": "remark",
}
LABEL_CN_TOTAL = "价税合计（大写）："
LABEL_LOWER = "（小写）"
LABEL_SUMMARY = "合计："
TABLE_HEADER_WORDS = ("项目名称", "金额", "税率", "税额")

# 票种标题（生成器 TYPE_PDF_TITLE）-> InvoiceCard.invoice_type：精确匹配
TITLE_TO_TYPE = {
    "电子发票（普通发票）": "数电普票",
    "电子发票（增值税专用发票）": "数电专票",
    "增值税电子普通发票": "电子普票",
    "增值税专用发票": "纸质专票",
    "增值税普通发票": "纸质普票",
}
_REQUIRED_FIELDS = ("invoice_number", "invoice_type", "issue_date")
_CONF_DROP_PENALTY = 0.2    # 非法数值被丢弃
_LINE_TOLERANCE = 2.0       # 同一行判定（top 差，pt）
_COL_TOLERANCE = 30.0       # 明细词归列的 x0 容差（pt）


def parse(path: str) -> InvoiceCard:
    """解析一个版式发票 PDF（文本层）为 InvoiceCard。"""
    pdfplumber = _import_pdfplumber()
    try:
        with pdfplumber.open(path) as pdf:
            page_words = [_line_words(page.extract_words() or [])
                          for page in pdf.pages]
    except ParserError:
        raise
    except Exception as exc:  # pdfminer 各类语法/密码异常统一转结构失败
        raise ParserError("PDF 解析失败: %s（%s）" % (path, exc)) from exc

    lines = [(page_no + 1, top, words)
             for page_no, line_groups in enumerate(page_words)
             for top, words in line_groups]
    if not lines:
        raise ParserError("结构失败：PDF 无文本层（%s）" % path)
    return _card_from_lines(lines, path)


def _import_pdfplumber():
    from ..utils import import_optional

    return import_optional("pdfplumber", "parse")


def _line_words(words: List[Dict[str, Any]]) -> List[Tuple[float, List[Dict[str, Any]]]]:
    """词按 top 聚成行；行内按 x0 排序。top 以行内最小值为准。"""
    ordered = sorted(words, key=lambda w: (w.get("top", 0.0), w.get("x0", 0.0)))
    rows: List[Tuple[float, List[Dict[str, Any]]]] = []
    for word in ordered:
        text = str(word.get("text") or "").strip()
        if not text:
            continue
        top = float(word.get("top", 0.0))
        if rows and abs(top - rows[-1][0]) <= _LINE_TOLERANCE:
            rows[-1][1].append(word)
        else:
            rows.append((top, [word]))
    return rows


def _card_from_lines(lines: List[Tuple[int, float, List[Dict[str, Any]]]],
                     path: str) -> InvoiceCard:
    confidence = 1.0
    field_flags: List[str] = []
    evidence: List[Evidence] = []
    found: Dict[str, Tuple[str, int, float]] = {}  # field -> (value, page, top)

    title = _find_title_type(lines)
    if title is None:
        raise ParserError("结构失败：无法识别票种标题（%s）" % path)
    found["invoice_type"] = title  # (票种, 页码, 标题行 top) 三元组

    header_row: Optional[Tuple[int, float, Dict[str, float]]] = None
    summary_top: Optional[Tuple[int, float]] = None
    for page, top, words in lines:
        for word in words:
            text = str(word.get("text") or "").strip()
            if text in TABLE_HEADER_WORDS:
                header_row = (page, top, _column_anchors(words))
                break
            if text.startswith(LABEL_SUMMARY) and summary_top is None:
                summary_top = (page, top)

    for page, top, words in lines:
        labels = _labels_on_line(words)
        for idx, (word, label, field) in enumerate(labels):
            if field in found:
                continue
            stop_x = labels[idx + 1][0].get("x0") if idx + 1 < len(labels) else None
            value_words = [w for w in words
                           if w.get("x0", 0) > word.get("x1", 0)
                           and (stop_x is None or w.get("x0", 0) < stop_x)]
            raw_parts = [str(w.get("text") or "") for w in value_words]
            if field == "remark":
                found[field] = (" ".join(p.strip() for p in raw_parts if p.strip()),
                                page, top)
                continue
            found[field] = ("".join(p.strip() for p in raw_parts), page, top)

    # 主键三要素缺失即结构失败（不猜值纪律）
    for field in _REQUIRED_FIELDS:
        if field not in found or not found[field][0].strip():
            hint = "未能定位 %s 标签" % field
            raise ParserError("结构失败：%s（%s）" % (hint, path))

    card_kwargs: Dict[str, Any] = {}
    for field in _REQUIRED_FIELDS:
        value, page, top = found[field]
        card_kwargs[field] = value.strip()
        evidence.append(Evidence(source_file=path, quote=value.strip(),
                                 location="p%d@y%.1f" % (page, top)))

    # 头部文本字段
    for field in ("buyer_name", "buyer_tax_id", "seller_name", "seller_tax_id",
                  "remark"):
        if field in found:
            value, page, top = found[field]
            if not value.strip():
                field_flags.append("%s#missing" % field)
                continue
            card_kwargs[field] = value.strip()
            evidence.append(Evidence(source_file=path, quote=value.strip(),
                                     location="p%d@y%.1f" % (page, top)))
        else:
            field_flags.append("%s#absent" % field)

    # 汇总区：合计（金额+税额）、大写、（小写）
    summary_raw = _line_value_after(LABEL_SUMMARY, lines)
    if summary_raw:
        amount, tax, ok = _split_summary(summary_raw)
        if ok:
            card_kwargs["amount"] = amount
            card_kwargs["tax_amount"] = tax
            evidence.append(Evidence(source_file=path, quote=summary_raw,
                                     location=_label_location(LABEL_SUMMARY, lines)))
        else:
            field_flags.append("amount#summary_unparsed")
            field_flags.append("tax_amount#summary_unparsed")
    else:
        field_flags.append("amount#absent")
        field_flags.append("tax_amount#absent")

    cn_raw = _cn_total(lines)
    if cn_raw:
        card_kwargs["total_with_tax_cn"] = cn_raw
        evidence.append(Evidence(source_file=path, quote=cn_raw,
                                 location=_label_location(LABEL_CN_TOTAL, lines)))
    else:
        field_flags.append("total_with_tax_cn#absent")

    lower_raw = _lower_total(lines)
    if lower_raw:
        kept, ok = _clean_numeric_value(lower_raw)
        if ok:
            card_kwargs["total_with_tax"] = kept
        else:
            confidence -= _CONF_DROP_PENALTY
            field_flags.append("total_with_tax#invalid_number_dropped")
    else:
        field_flags.append("total_with_tax#absent")

    # 明细表
    items = _parse_items(lines, header_row, summary_top, path, field_flags, evidence)
    card_kwargs["items"] = items
    card_kwargs["confidence"] = max(0.0, confidence)
    card_kwargs["field_flags"] = field_flags
    card_kwargs["evidence"] = evidence
    return InvoiceCard(**card_kwargs)  # type: ignore[arg-type]


def _find_title_type(lines) -> Optional[Tuple[str, int, float]]:
    """票种标题：全词精确匹配标题词典，取最靠上的命中 -> (票种, 页码, top)。"""
    best: Optional[Tuple[float, str, int]] = None
    for page, top, words in lines:
        for word in words:
            text = str(word.get("text") or "").strip()
            if text in TITLE_TO_TYPE and (best is None or top < best[0]):
                best = (top, TITLE_TO_TYPE[text], page)
    return (best[1], best[2], best[0]) if best else None


def _labels_on_line(words: List[Dict[str, Any]]):
    """行内识别出的标签词列表 [(word, label, field)]，按 x0 排序。"""
    hits = []
    for word in words:
        text = str(word.get("text") or "").replace(" ", "")
        for label, field in LABEL_FIELDS.items():
            if text.startswith(label):
                hits.append((word, label, field))
                break
    hits.sort(key=lambda hit: hit[0].get("x0", 0.0))
    return hits


def _line_value_after(prefix: str, lines) -> str:
    """首个以 prefix 开头的词：前缀后文本 + 同词行右侧后续词拼接。"""
    for page, top, words in lines:
        for idx, word in enumerate(words):
            text = str(word.get("text") or "").replace(" ", "")
            if not text.startswith(prefix):
                continue
            rest = text[len(prefix):].strip()
            tail = [str(w.get("text") or "").strip() for w in words[idx + 1:]]
            return " ".join([rest] + [t for t in tail if t]).strip()
        # prefix 词可能是独立词（标签单独成词）：右侧词为其值
        for idx, word in enumerate(words):
            text = str(word.get("text") or "").strip()
            if text == prefix.rstrip("：") or text == prefix:
                tail = [str(w.get("text") or "").strip() for w in words[idx + 1:]]
                return " ".join(t for t in tail if t).strip()
    return ""


def _cn_total(lines) -> str:
    """大写金额：标签+值同词合并（值起点与标签尾重叠）或分离两种形态。"""
    for page, top, words in lines:
        for word in words:
            text = str(word.get("text") or "").replace(" ", "")
            if text.startswith(LABEL_CN_TOTAL):
                value = text[len(LABEL_CN_TOTAL):]
                if value:
                    return value
                tail = [str(w.get("text") or "").strip()
                        for w in words if w is not word and w.get("x0", 0) > word.get("x1", 0)]
                return "".join(t for t in tail if t)
    return ""


def _lower_total(lines) -> str:
    """小写金额：`（小写）￥X` 词剥前缀；兼容独立 ￥X 词兜底。"""
    for page, top, words in lines:
        for word in words:
            text = str(word.get("text") or "").replace(" ", "")
            if text.startswith(LABEL_LOWER) and len(text) > len(LABEL_LOWER):
                return text[len(LABEL_LOWER):]
    for page, top, words in lines:
        for word in words:
            text = str(word.get("text") or "")
            if text.startswith("￥") or text.startswith("¥"):
                return text
    return ""


def _split_summary(raw: str) -> Tuple[str, str, bool]:
    """`51097.17（税额 4743.68）` -> (amount, tax, ok)；数值清洗各自过校验。"""
    marker = "（税额"
    if marker not in raw or not raw.rstrip().endswith("）"):
        return "", "", False
    left, right = raw.split(marker, 1)
    amount, amount_ok = _clean_numeric_value(left)
    tax, tax_ok = _clean_numeric_value(right.rstrip().rstrip("）"))
    return amount, tax, amount_ok and tax_ok


def _clean_numeric_value(raw: str) -> Tuple[str, bool]:
    cleaned = clean_numeric_text(raw or "")
    if not cleaned or not is_decimal_text(cleaned):
        return "", False
    from decimal import Decimal, InvalidOperation

    try:
        Decimal(cleaned)
    except InvalidOperation:
        return "", False
    return cleaned, True


def _column_anchors(words: List[Dict[str, Any]]) -> Dict[str, float]:
    anchors: Dict[str, float] = {}
    for word in words:
        text = str(word.get("text") or "").strip()
        if text in TABLE_HEADER_WORDS:
            anchors[text] = float(word.get("x0", 0.0))
    return anchors


def _parse_items(lines, header_row, summary_top, path, field_flags,
                 evidence) -> List[LineItem]:
    """明细行：表头列锚点 +（表头, 合计）之间的行按 x0 最近列归并。"""
    if header_row is None:
        return []
    page_h, top_h, anchors = header_row
    if len(anchors) < len(TABLE_HEADER_WORDS):
        return []
    limit_top = None
    if summary_top is not None:
        page_s, top_s = summary_top
        if page_s == page_h and top_s > top_h:
            limit_top = top_s
    rows: Dict[int, Dict[str, str]] = {}
    for page, top, words in lines:
        if page != page_h or top <= top_h or (limit_top is not None and top >= limit_top):
            continue
        for word in words:
            text = str(word.get("text") or "").strip()
            if not text or text in TABLE_HEADER_WORDS:
                continue
            x0 = float(word.get("x0", 0.0))
            column = min(TABLE_HEADER_WORDS,
                         key=lambda name: abs(anchors[name] - x0))
            if abs(anchors[column] - x0) > _COL_TOLERANCE:
                continue
            row = rows.setdefault(round(top, 1), {})
            if column == "项目名称":
                row.setdefault("name", text)
            elif column == "金额":
                row.setdefault("amount", text)
            elif column == "税率":
                row.setdefault("tax_rate", text)
            else:
                row.setdefault("tax_amount", text)
    items: List[LineItem] = []
    for row_top in sorted(rows):
        row = rows[row_top]
        name = row.get("name", "")
        amount, amount_ok = _clean_numeric_value(row.get("amount", ""))
        tax, tax_ok = _clean_numeric_value(row.get("tax_amount", ""))
        rate_raw = row.get("tax_rate")
        if rate_raw is None:
            rate, rate_ok = "", True   # 末行缺税率为合法形态（TEMPLATE_REFERENCE §2）
        else:
            rate, rate_ok = _clean_numeric_value(rate_raw)
        for cell, ok in (("amount", amount_ok), ("tax_rate", rate_ok),
                         ("tax_amount", tax_ok)):
            if not ok:
                field_flags.append("items[%d].%s#invalid_number_dropped"
                                   % (len(items) + 1, cell))
        quote = " ".join(row.get(cell, "") for cell in
                         ("name", "amount", "tax_rate", "tax_amount")).strip()
        evidence.append(Evidence(source_file=path, quote=quote,
                                 location="p%d@y%.1f" % (page_h, row_top)))
        items.append(LineItem(name=name, amount=amount, tax_rate=rate,
                              tax_amount=tax))
    return items


def _label_location(label: str, lines) -> str:
    for page, top, words in lines:
        for word in words:
            text = str(word.get("text") or "").replace(" ", "")
            if text.startswith(label):
                return "p%d@y%.1f" % (page, top)
    return "p1"
