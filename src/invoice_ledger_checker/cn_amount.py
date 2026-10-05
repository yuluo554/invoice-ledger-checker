"""人民币小写金额 -> 中文大写金额（纯 stdlib，生成器与 R-ARITH-02 共用）。

- 生成器（M1）：发票卡 total_with_tax_cn 由此产出，保证票面大小写自洽；
- 规则 R-ARITH-02（M3）：大写金额一致性检测复用本模块（转换表自带，
  plan/04 §3"纯 stdlib"约定）。

大写规则（财务惯例）：
- 数字：零壹贰叁肆伍陆柒捌玖；组内位单位：拾佰仟，组单位：万/亿/万亿
  （每 4 位一组，组单位只在组尾挂一次：1234567 -> 壹佰贰拾叁万肆仟…）；
- 中间连续零只写一个"零"，末尾零不写（105000 -> 壹拾万零伍仟）；
- 角分：角>0 写"X角"；角=0 且分>0 且有元部时先补"零"（1130.05 -> …元零伍分）；
  分=0 且角=0 时以"整"收尾；无元部时角/分直接开头（0.50 -> 伍角）；
- 输入为 Decimal 可解析的非负金额文本，超两位小数按四舍五入取分。
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_DIGITS = "零壹贰叁肆伍陆柒捌玖"
_INNER = ("", "拾", "佰", "仟")          # 组内位单位（个位起）
_GROUP_UNITS = ("", "万", "亿", "万亿")   # 4 位一组的组单位


def _integer_to_cn(number: int) -> str:
    """非零正整数 -> 大写（组单位挂组尾、中间零合并、末尾零丢弃）。"""
    if number < 0:
        raise ValueError("整数部必须非负: %d" % number)
    if number == 0:
        return "零"
    text = str(number)
    if len(text) > 16:
        raise ValueError("金额整数部超出可表示范围（>=万亿亿）: %s" % text)
    parts = []
    group_dirty = False   # 当前组内是否输出过非零数字（决定组单位是否挂）
    zero_pending = False
    for index, ch in enumerate(text):
        pos = len(text) - 1 - index       # 个位起的位置
        group_idx, inner_pos = divmod(pos, 4)
        if inner_pos == 3 and index > 0 and group_dirty:
            # 进入新组：给刚结束的组挂组单位
            parts.append(_GROUP_UNITS[group_idx + 1])
            group_dirty = False
        digit = int(ch)
        if digit == 0:
            zero_pending = True
            continue
        if zero_pending and parts:
            parts.append("零")
        zero_pending = False
        group_dirty = True
        parts.append(_DIGITS[digit] + _INNER[inner_pos])
    return "".join(parts)


def encode_amount(value: str) -> str:
    """金额文本（如 "1130.00"）-> 中文大写（如 "壹仟壹佰叁拾元整"）。

    负数与不可解析输入抛 ValueError（调用侧按"票面异常"处理，不静默）。
    """
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("金额不可解析: %r" % (value,)) from exc
    if amount < 0:
        raise ValueError("金额不能为负: %s" % amount)
    fen_total = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
    yuan, frac = divmod(fen_total, 100)
    jiao, fen = divmod(frac, 10)

    parts = []
    if yuan:
        parts.append(_integer_to_cn(yuan) + "元")
    if jiao:
        parts.append(_DIGITS[jiao] + "角")
    elif fen and yuan:
        parts.append("零")  # 有元部、角为零、分非零：元与分之间补零
    if fen:
        parts.append(_DIGITS[fen] + "分")
    if not parts:
        return "零元整"
    if not (jiao or fen):
        parts.append("整")
    return "".join(parts)
