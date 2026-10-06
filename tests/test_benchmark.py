"""benchmark 命令与基准模块测试（M4，CLI 形态；口径同 tests/test_baseline_detection）。

纪律：pdfplumber 为重依赖，函数内显式 skip（与 test_baseline_detection.py 一致，
防"静默少跑"——收集数必须一致）。锚点数字（18 对真值异常/13 findings）与
M3 冻结对拍锚点同源，改数据/改规则会打挂本文件，属预期回归门。
"""

import importlib.util
from pathlib import Path

import pytest

from invoice_ledger_checker.benchmarks import benchmark as benchmark_mod
from invoice_ledger_checker.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
HAS_DATA = (DATA_DIR / "ground_truth" / "manifest.json").is_file()

requires_data = pytest.mark.skipif(
    not HAS_DATA, reason="data/ground_truth 冻结真值不在仓（generate 可重建）")
requires_pdfplumber = pytest.mark.skipif(
    importlib.util.find_spec("pdfplumber") is None,
    reason="pdfplumber 未安装（CI 无重依赖路径）")


def _run_metrics():
    return benchmark_mod.run_benchmark(str(DATA_DIR))


@requires_data
@requires_pdfplumber
def test_run_benchmark_hits_all_gates():
    """冻结 60 份全量基准：门槛全过、锚点数字与 M3 冻结对拍一致。"""
    metrics = _run_metrics()
    parse = metrics["parse"]
    assert parse["files_total"] == 60
    assert parse["parsed_count"] == 57          # 60 - 3 OFD 顺延
    assert len(parse["deferred_ofd"]) == 3
    assert all(p.endswith(".ofd") for p in parse["deferred_ofd"])
    assert parse["failed_files"] == []
    assert parse["mismatches"] == []
    assert len(parse["fields"]) == 16           # 12 卡级字段 + 4 明细字段
    assert parse["macro"]["f1"] >= benchmark_mod.PARSE_F1_MIN
    assert parse["micro"]["f1"] == pytest.approx(1.0)

    detect = metrics["detect"]
    assert detect["numbers_expected"] == 58     # 60 文件 - EXACT/JOINT 同号副本各 1
    assert detect["truth_anomalies"] == 18      # DUP-01×2 DUP-02×1 DUP-03×2 SEQ×5 其余各×2
    assert detect["alerts"] == 18
    assert (detect["tp"], detect["fp"], detect["fn"], detect["level_mismatch"]) == (18, 0, 0, 0)
    assert detect["findings_total"] == 13
    assert detect["detection_rate"] == pytest.approx(1.0)
    assert detect["false_positive_rate"] == 0.0
    assert detect["level_accuracy"] == pytest.approx(1.0)
    assert detect["unknown_numbers"] == []
    assert metrics["anchors_missing"] == []
    assert benchmark_mod.gate_failures(metrics) == []


@requires_data
@requires_pdfplumber
def test_report_is_deterministic_and_registers_ofd(tmp_path):
    """零 API 可重复守门：同输入重跑报告逐字节一致（无墙钟）；OFD 顺延显式登记。"""
    report_a = tmp_path / "a.md"
    report_b = tmp_path / "b" / "nested.md"     # 父目录不存在时应自动创建
    metrics = _run_metrics()
    benchmark_mod.write_report(metrics, str(report_a))
    benchmark_mod.write_report(metrics, str(report_b))
    bytes_a = report_a.read_bytes()
    assert bytes_a == report_b.read_bytes()
    assert b"\r" not in bytes_a                 # LF 行尾（与 .gitattributes eol=lf 一致）
    text = bytes_a.decode("utf-8")
    for path in metrics["parse"]["deferred_ofd"]:
        assert path in text                     # OFD 3 份逐份登记
    assert "1.0000" in text and "100.00%" in text


@requires_data
@requires_pdfplumber
def test_cli_benchmark_exit_zero_writes_report(tmp_path, capsys):
    """DoD 命令形态：一条命令出指标表 + 报告落盘 + 门槛通过退出码 0。"""
    report = tmp_path / "report.md"
    rc = main(["benchmark", "--data", str(DATA_DIR), "--report", str(report)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "宏平均" in out and "检出率" in out and "门槛断言" in out
    assert report.is_file()


def test_cli_benchmark_missing_data_dir_exits_two(capsys):
    assert main(["benchmark", "--data", "definitely/not/a/dir"]) == 2
    assert "数据目录不存在" in capsys.readouterr().out


@requires_data
def test_cli_benchmark_missing_truth_files_exits_two(tmp_path, capsys):
    """数据目录存在但缺真值 JSON -> 参数错误退出码 2（不做半途崩溃）。"""
    (tmp_path / "invoices").mkdir()
    rc = main(["benchmark", "--data", str(tmp_path)])
    assert rc == 2
    assert "缺 ground_truth" in capsys.readouterr().out


@requires_data
@requires_pdfplumber
def test_gate_failures_flags_each_regression():
    """门槛断言逐项触发（人为劣化指标，验证回归信号不漏报）。"""
    metrics = _run_metrics()
    metrics["parse"]["macro"]["f1"] = 0.90
    metrics["parse"]["mismatches"] = [{"path": "x", "field": "y",
                                       "expected": "1", "actual": "2"}]
    metrics["detect"]["detection_rate"] = 0.8
    metrics["detect"]["false_positive_rate"] = 0.1
    metrics["detect"]["level_accuracy"] = 0.9
    metrics["detect"]["unknown_numbers"] = ["123"]
    metrics["anchors_missing"] = ["batch_04"]
    failures = benchmark_mod.gate_failures(metrics)
    assert len(failures) == 7                   # 解析F1/不一致/检出率/误报/判定/未知号/锚点
    assert any("F1" in f for f in failures)
    assert any("字段级不一致" in f for f in failures)
    assert any("检出率" in f for f in failures)
    assert any("误报率" in f for f in failures)
    assert any("判定准确率" in f for f in failures)
    assert any("expense_anchor" in f for f in failures)
