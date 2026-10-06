"""CLI 集成测试：子进程跑真实入口（编码/退出码契约，Windows GBK 防线）。"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"


def run_cli(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "invoice_ledger_checker", *args],
        capture_output=True,
        encoding="utf-8",
        env=env,
        timeout=120,
    )


def test_help_exits_zero():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "demo" in result.stdout


def test_no_command_exits_two_with_help():
    result = run_cli()
    assert result.returncode == 2
    assert "demo" in result.stdout


def test_version_flag():
    result = run_cli("--version")
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_demo_full_pipeline():
    result = run_cli("demo")
    assert result.returncode == 0
    # 演示叙事：3 张合成票入库 2 张（同号拒收 1）+ 2 条异常
    assert "入库 2 张" in result.stdout
    assert "R-DUP-01" in result.stdout
    assert "R-ARITH-01" in result.stdout


def test_doctor_reports_optional_deps():
    result = run_cli("doctor")
    assert result.returncode == 0
    assert "pdfplumber" in result.stdout
    assert "PySide6" in result.stdout


def test_stub_commands_exit_two_with_milestone_hint():
    for command, milestone in [
        ("check", "M3"),
        ("export", "M5"),
        ("app", "M5"),
    ]:
        result = run_cli(command)
        assert result.returncode == 2, command
        assert milestone in result.stdout, command


def test_parse_missing_dir_exits_two():
    result = run_cli("parse", "definitely/not/a/dir")
    assert result.returncode == 2
    assert "目录不存在" in result.stdout


def test_parse_xml_dataset_with_bad_file(tmp_path):
    """XML 数据集全解析 + 坏文件记拒绝清单不崩溃（退出码 0）。"""
    out_dir = tmp_path / "data"
    gen = run_cli("generate", "--out", str(out_dir), "--seed", "7",
                  "--n", "8", "--formats", "xml")
    assert gen.returncode == 0, gen.stderr
    invoices = out_dir / "invoices"
    (invoices / "batch_01" / "99900000000000000000.xml").write_bytes(
        b"<not-an-invoice/>")

    result = run_cli("parse", str(invoices), "--report")
    assert result.returncode == 0, result.stderr
    assert "成功解析 8 张卡" in result.stdout
    assert "99900000000000000000.xml" in result.stdout
    assert "拒绝清单: 1 个" in result.stdout


def test_parse_frozen_data_full_report():
    """冻结 60 份全量解析：57 成功 + OFD 3 顺延登记（CI 无 pdfplumber 时跳过）。"""
    if importlib.util.find_spec("pdfplumber") is None:
        pytest.skip("pdfplumber 未安装（CI 无重依赖路径）")
    invoices = Path(__file__).resolve().parents[1] / "data" / "invoices"
    if not invoices.is_dir():
        pytest.skip("data/invoices 冻结数据不在仓")
    result = run_cli("parse", str(invoices), "--report")
    assert result.returncode == 0, result.stderr
    assert "成功解析 57 张卡" in result.stdout
    assert "xml 成功 35" in result.stdout
    assert "pdf 成功 22" in result.stdout
    assert "OFD 顺延登记: 3 个文件未解析" in result.stdout
    assert "拒绝清单: 无" in result.stdout


def test_generate_produces_dataset(tmp_path):
    """generate 一键产出数据集 + 真值（CI 无 reportlab 时降级 xml,ofd）。"""
    has_reportlab = importlib.util.find_spec("reportlab") is not None
    formats = "xml,pdf,ofd" if has_reportlab else "xml,ofd"
    out_dir = tmp_path / "data"
    result = run_cli(
        "generate", "--out", str(out_dir), "--seed", "7", "--n", "12",
        "--formats", formats,
    )
    assert result.returncode == 0, result.stderr
    assert "全虚构" in result.stdout
    manifest = (out_dir / "ground_truth" / "manifest.json").read_text(encoding="utf-8")
    assert '"seed": 7' in manifest
    assert (out_dir / "ground_truth" / "cards.json").exists()
    assert (out_dir / "ground_truth" / "expectations.json").exists()


def test_generate_rejects_bad_formats(tmp_path):
    result = run_cli("generate", "--out", str(tmp_path), "--formats", "pdf")
    assert result.returncode == 2
    assert "参数错误" in result.stdout
