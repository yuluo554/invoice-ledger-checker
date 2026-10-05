"""中文大写金额转换测试（生成器与 R-ARITH-02 共用模块）。"""

import pytest

from invoice_ledger_checker.cn_amount import encode_amount


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0.00", "零元整"),
        ("10.00", "壹拾元整"),
        ("20.00", "贰拾元整"),
        ("110.00", "壹佰壹拾元整"),
        ("1130.00", "壹仟壹佰叁拾元整"),
        ("2120.00", "贰仟壹佰贰拾元整"),
        ("1002.50", "壹仟零贰元伍角"),
        ("1130.50", "壹仟壹佰叁拾元伍角"),
        ("1130.05", "壹仟壹佰叁拾元零伍分"),
        ("110.05", "壹佰壹拾元零伍分"),
        ("105000.00", "壹拾万零伍仟元整"),
        ("100010000.00", "壹亿零壹万元整"),
        ("100000001.00", "壹亿零壹元整"),
        ("0.50", "伍角"),
        ("0.05", "伍分"),
        ("0.55", "伍角伍分"),
        ("1234567.89", "壹佰贰拾叁万肆仟伍佰陆拾柒元捌角玖分"),
    ],
)
def test_encode_known_values(value, expected):
    assert encode_amount(value) == expected


def test_encode_rounds_extra_decimals():
    # ROUND_HALF_UP 到分：1.004 -> 1.00，1.005/1.006 -> 1.01（壹元零壹分）
    assert encode_amount("1.004") == "壹元整"
    assert encode_amount("1.005") == "壹元零壹分"
    assert encode_amount("1.006") == "壹元零壹分"


def test_encode_rejects_negative_and_garbage():
    with pytest.raises(ValueError):
        encode_amount("-1.00")
    with pytest.raises(ValueError):
        encode_amount("不是金额")
