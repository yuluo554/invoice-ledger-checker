"""字段级解析对账（M2 自测 F1 初测；M4 字段解析基准同源复用）。

口径权威出处：generator/synthetic.py 模块注释 §2——真值卡 dict vs 解析卡
dict **字段级**对账，items 展开为 items[i].field；evidence/confidence/
field_flags/batch_id 是解析层自由度，不参与对账；INJ-FIELD-MISS 缺失字段
真值为空串，解析产出其他值即误报（空==空按正确计）。
"""

from typing import Any, Dict, List, Tuple

# 不参与对账的卡级键（解析层自由度，见生成器模块注释 §1）
NON_COMPARED_KEYS = frozenset({"batch_id", "confidence", "field_flags", "evidence"})
ITEM_FIELDS = ("name", "amount", "tax_rate", "tax_amount")


def flatten_card(card: Dict[str, Any], item_count: int = -1) -> Dict[str, str]:
    """InvoiceCard dict -> 扁平 {字段路径: 文本值}；item_count<0 用卡自身行数。

    两侧用同一 item_count 展开后键集对齐：行数多的一侧多出的行按空串对
    侧计错（多解析出的明细行是误报，少解析的是漏报）。
    """
    out: Dict[str, str] = {}
    for key, value in card.items():
        if key in NON_COMPARED_KEYS or key == "items":
            continue
        out[key] = "" if value is None else str(value)
    items = card.get("items") or []
    n = len(items) if item_count < 0 else item_count
    for idx in range(n):
        row = items[idx] if idx < len(items) else {}
        for cell in ITEM_FIELDS:
            value = row.get(cell) if isinstance(row, dict) else None
            out["items[%d].%s" % (idx, cell)] = "" if value is None else str(value)
    return out


def compare(truth: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    """真值卡 vs 解析卡字段级对账：返回 P/R/F1 与不一致清单（M4 同口径）。

    P/R/F1 按扁平字段计：两侧相等（含双双为空）计 TP；解析有真值无计 FP；
    真值有解析无计 FN；两侧均有但不等计 FP+FN 各一。
    """
    n_items = max(len(truth.get("items") or []), len(parsed.get("items") or []))
    truth_flat = flatten_card(truth, n_items)
    parsed_flat = flatten_card(parsed, n_items)
    tp = fp = fn = 0
    mismatches: List[Tuple[str, str, str]] = []
    for key in sorted(set(truth_flat) | set(parsed_flat)):
        expected = truth_flat.get(key)
        actual = parsed_flat.get(key)
        if expected == actual:
            tp += 1
            continue
        if expected is None:
            fp += 1          # 解析多出的字段（正常不应发生：两侧同 schema）
        elif actual is None:
            fn += 1
        else:
            fp += 1
            fn += 1
            mismatches.append((key, expected, actual))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 1.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fields": tp + fp,      # 真值侧字段总数（=TP+FN）
        "mismatches": mismatches,
    }
