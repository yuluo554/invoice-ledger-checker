"""Excel 导出契约测试（M5，FR-20：双 sheet + 条件格式标红可断言）。

openpyxl 属 extras: export 重依赖——函数内检测缺失时显式 skip（计数上报
纪律，plan/03 §4）；样式断言直接读回工作簿（条件格式规则/填充色/表头）。
"""

import pytest

from invoice_ledger_checker.export.excel import (
    FINDING_HEADERS,
    INVOICE_HEADERS,
    export_ledger,
)
from invoice_ledger_checker.models import InvoiceCard, LineItem
from invoice_ledger_checker.storage import Ledger
from invoice_ledger_checker.utils import OptionalDependencyError


def _require_openpyxl():
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        pytest.skip("openpyxl 未安装（无 export extras 路径，显式 skip 计数）")


def _build_ledger(path):
    """两批发票 + 三级 finding 各一条（覆盖条件格式三分支）。"""
    ledger = Ledger(str(path))
    ledger.create_batch("b1", source_desc="测试批次", file_count=2)
    ledger.add_invoice(
        InvoiceCard(
            invoice_number="25910000000000123456",
            invoice_type="数电普票",
            issue_date="2026-01-05",
            buyer_name="星辰科技有限公司",
            seller_name="云图商贸有限公司",
            seller_tax_id="91330100DEMOFAKE02",
            items=[LineItem(name="会议服务费", amount="1000.00",
                            tax_rate="0.13", tax_amount="130.00")],
            amount="1000.00",
            tax_amount="130.00",
            total_with_tax="1130.00",
            total_with_tax_cn="壹仟壹佰叁拾元整",
            batch_id="b1",
        ),
        "b1",
    )
    ledger.add_invoice(
        InvoiceCard(
            invoice_number="25910000000000123457",
            invoice_type="数电专票",
            issue_date="2026-02-10",
            seller_name="云图商贸有限公司",
            items=[LineItem(name="咨询费", amount="2000.00",
                            tax_rate="0.06", tax_amount="120.00")],
            amount="2000.00",
            tax_amount="120.00",
            total_with_tax="9999.00",  # 算术错卡
            field_flags=["total_with_tax#low_conf"],
            batch_id="b1",
        ),
        "b1",
    )
    for level, rule, numbers in [
        ("error", "R-ARITH-01", ["25910000000000123457"]),
        ("suspicious", "R-DUP-03", ["25910000000000123456"]),
        ("review", "R-TIME-02", ["25910000000000123456"]),
    ]:
        ledger.add_finding({
            "finding_id": "%s:%s" % (rule, "|".join(numbers)),
            "rule_id": rule,
            "level": level,
            "invoice_numbers": numbers,
            "message": "测试用 %s 事实" % level,
            "evidence": {},
        }, batch_id="b1")
    return ledger


def test_export_double_sheets_headers_and_rows(tmp_path):
    """双 sheet、表头与数据行、条件格式规则三分支齐备（DoD 样式断言）。"""
    _require_openpyxl()
    from openpyxl import load_workbook

    db = tmp_path / "ledger.db"
    ledger = _build_ledger(db)
    ledger.close()

    out = tmp_path / "out.xlsx"
    summary = export_ledger(str(db), str(out))
    assert summary["invoice_count"] == 2
    assert summary["finding_count"] == 3
    assert summary["sheets"] == ["发票台账", "异常清单"]
    assert out.is_file()

    wb = load_workbook(str(out))
    assert wb.sheetnames == ["发票台账", "异常清单"]

    inv = wb["发票台账"]
    assert [c.value for c in inv[1]] == INVOICE_HEADERS
    row2 = [c.value for c in inv[2]]
    assert row2[0] == "25910000000000123456"
    assert row2[2] == "2026-01-05"
    # 金额列导出为数值单元格（显示层转换；空串仍为空；整数值 openpyxl 回读为 int）
    assert isinstance(row2[9], (int, float)) and abs(row2[9] - 1130.0) < 1e-9
    assert isinstance(inv.cell(row=3, column=10).value, (int, float))

    findings = wb["异常清单"]
    assert [c.value for c in findings[1]] == FINDING_HEADERS
    levels = {findings.cell(row=r, column=4).value for r in (2, 3, 4)}
    assert levels == {"确认异常", "疑似", "待人工确认"}
    assert findings.cell(row=2, column=2).value == "R-ARITH-01"
    assert findings.cell(row=2, column=3).value == "价税合计复核"


def test_conditional_formatting_rules_styles(tmp_path):
    """条件格式标红：级别列三分支公式与填充色逐一断言（DoD 核心样式）。"""
    _require_openpyxl()
    from openpyxl import load_workbook

    db = tmp_path / "ledger.db"
    _build_ledger(db).close()
    out = tmp_path / "out.xlsx"
    export_ledger(str(db), str(out))

    wb = load_workbook(str(out))
    findings = wb["异常清单"]
    rules = []
    for rng in findings.conditional_formatting:
        rules.extend(rng.rules)
    assert len(rules) == 3
    by_fill = {}
    for rule in rules:
        assert rule.type == "expression"
        formula = rule.formula[0]
        assert formula.startswith('$D2="') and formula.endswith('"')
        by_fill[rule.dxf.fill.bgColor.rgb] = formula
    # error=红 / suspicious=黄 / review=蓝，公式命中级别显示名
    assert by_fill["00FFC7CE"] == '$D2="确认异常"'
    assert by_fill["00FFEB9C"] == '$D2="疑似"'
    assert by_fill["00BDD7EE"] == '$D2="待人工确认"'

    inv = wb["发票台账"]
    inv_rules = []
    for rng in inv.conditional_formatting:
        inv_rules.extend(rng.rules)
    assert len(inv_rules) == 1  # 字段标记非空 -> 浅黄提示
    assert inv_rules[0].formula[0] == '$P2<>""'
    assert inv_rules[0].dxf.fill.bgColor.rgb == "00FFF2CC"


def test_export_missing_db_raises_value_error(tmp_path):
    with pytest.raises(ValueError):
        export_ledger(str(tmp_path / "nope.db"), str(tmp_path / "o.xlsx"))


def test_export_missing_openpyxl_raises_hint(tmp_path, monkeypatch):
    """缺 openpyxl -> OptionalDependencyError 带安装提示（CLI 捕获转 exit 2）。"""

    def _raise(module_name, extra):
        raise OptionalDependencyError(module_name, extra)

    db = tmp_path / "ledger.db"
    _build_ledger(db).close()
    monkeypatch.setattr(
        "invoice_ledger_checker.export.excel.import_optional", _raise)
    with pytest.raises(OptionalDependencyError) as excinfo:
        export_ledger(str(db), str(tmp_path / "o.xlsx"))
    assert "[export]" in str(excinfo.value)
