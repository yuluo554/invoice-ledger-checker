"""CLI 集成测试：子进程跑真实入口（编码/退出码契约，Windows GBK 防线）。"""

import os
import subprocess
import sys
from pathlib import Path

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
        ("generate", "M1"),
        ("parse", "M2"),
        ("check", "M3"),
        ("export", "M5"),
        ("app", "M5"),
    ]:
        result = run_cli(command)
        assert result.returncode == 2, command
        assert milestone in result.stdout, command
