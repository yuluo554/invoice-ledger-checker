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
        timeout=180,
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


def test_demo_end_to_end_all_rules():
    """demo 端到端（M3）：合成数据 -> 解析 -> 入库 -> 八规则检测。"""
    result = run_cli("demo")
    assert result.returncode == 0, result.stderr
    assert "端到端" in result.stdout
    assert "入库 58 张，主键拒收同号副本 2 张" in result.stdout
    assert "八规则全量" in result.stdout
    # 三级语义各举其一（error/suspicious/review 均有产出）
    assert "R-DUP-01" in result.stdout
    assert "R-ARITH-01" in result.stdout
    assert "R-SEQ-01" in result.stdout
    assert "R-TIME-02" in result.stdout


def test_doctor_reports_optional_deps():
    result = run_cli("doctor")
    assert result.returncode == 0
    assert "pdfplumber" in result.stdout
    assert "PySide6" in result.stdout


def test_export_missing_db_exits_two():
    result = run_cli("export", "definitely/not/a/ledger.db")
    assert result.returncode == 2
    assert "台账数据库不存在" in result.stdout


def test_export_pipeline_generates_xlsx(tmp_path):
    """generate -> check -> export 一键出 Excel（exit 0 + 摘要行）。"""
    if importlib.util.find_spec("openpyxl") is None:
        pytest.skip("openpyxl 未安装（无 export extras 路径）")
    out_dir = tmp_path / "data"
    gen = run_cli("generate", "--out", str(out_dir), "--seed", "7",
                  "--n", "12", "--formats", "xml")
    assert gen.returncode == 0, gen.stderr
    db_path = tmp_path / "ledger.db"
    chk = run_cli(
        "check", str(out_dir / "invoices"), "--db", str(db_path),
        "--anchor-manifest", str(out_dir / "ground_truth" / "manifest.json"),
    )
    assert chk.returncode == 0, chk.stderr
    result = run_cli("export", str(db_path))
    assert result.returncode == 0, result.stderr
    assert "发票台账:" in result.stdout
    assert "异常清单:" in result.stdout
    xlsx = tmp_path / "ledger.xlsx"
    assert xlsx.is_file()

    # --out 自定义路径
    custom = tmp_path / "自定义 台账.xlsx"
    result2 = run_cli("export", str(db_path), "--out", str(custom))
    assert result2.returncode == 0, result2.stderr
    assert custom.is_file()


def test_check_missing_dir_exits_two():
    result = run_cli("check", "definitely/not/a/dir")
    assert result.returncode == 2
    assert "目录不存在" in result.stdout


def test_check_generated_dataset(tmp_path):
    """generate -> check 一键入库+检测（基准通路 anchor manifest；XML 免重依赖）。"""
    out_dir = tmp_path / "data"
    gen = run_cli("generate", "--out", str(out_dir), "--seed", "7",
                  "--n", "30", "--formats", "xml")
    assert gen.returncode == 0, gen.stderr
    db_path = tmp_path / "ledger.db"
    result = run_cli(
        "check", str(out_dir / "invoices"), "--db", str(db_path),
        "--anchor-manifest", str(out_dir / "ground_truth" / "manifest.json"),
    )
    assert result.returncode == 0, result.stderr
    assert "成功解析 30 张卡" in result.stdout
    assert "主键拒收同号副本 2 张" in result.stdout
    assert "expense_anchor" in result.stdout        # 基准通路生效
    assert "R-DUP-01" in result.stdout              # 副本事件必触发
    assert "R-DUP-02" in result.stdout
    assert "R-SEQ-01" in result.stdout
    assert "findings 已落库" in result.stdout
    assert db_path.exists()


def test_check_rejects_bad_manifest(tmp_path):
    out_dir = tmp_path / "data"
    gen = run_cli("generate", "--out", str(out_dir), "--seed", "7",
                  "--n", "8", "--formats", "xml")
    assert gen.returncode == 0, gen.stderr
    bad_manifest = tmp_path / "broken.json"
    bad_manifest.write_text("{not json", encoding="utf-8")
    result = run_cli(
        "check", str(out_dir / "invoices"), "--db", str(tmp_path / "l.db"),
        "--anchor-manifest", str(bad_manifest),
    )
    assert result.returncode == 2
    assert "anchor manifest 不可读" in result.stdout


def test_check_frozen_data_full_pipeline(tmp_path):
    """DoD 命令实测：冻结 60 份 -> 入库 55 + 拒收 2 -> 13 条三级异常
    （CI 无 pdfplumber 时跳过）。"""
    if importlib.util.find_spec("pdfplumber") is None:
        pytest.skip("pdfplumber 未安装（CI 无重依赖路径）")
    invoices = Path(__file__).resolve().parents[1] / "data" / "invoices"
    if not invoices.is_dir():
        pytest.skip("data/invoices 冻结数据不在仓")
    result = run_cli(
        "check", str(invoices), "--db", str(tmp_path / "ledger.db"),
        "--anchor-manifest",
        str(Path(__file__).resolve().parents[1] / "data" / "ground_truth" / "manifest.json"),
    )
    assert result.returncode == 0, result.stderr
    assert "成功解析 57 张卡" in result.stdout
    assert "入库 55 张，主键拒收同号副本 2 张" in result.stdout
    assert "异常 13 条" in result.stdout
    assert "[error]" in result.stdout
    assert "[suspicious]" in result.stdout
    assert "[review]" in result.stdout


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
