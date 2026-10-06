# -*- coding: utf-8 -*-
"""发布脱敏回归门（M6）：扫描器自测 + 跟踪内容/历史/提交信息/元数据的清洁度。

对应 tools/sensitive_scan.py。这组测试断言两件事：① 扫描器本身可用（阳性+阴性双对照
通过，不因规则漂移而静默失效）；② 当前仓库干净（真实个人信息——邮箱/手机号/身份证/
个人目录/内网 IP/密钥——不得进入将要公开的仓库）。

后续任何提交把个人信息带进来，这里就会红——这正是发布门应当在 CI 里持续值守的原因。
"""

import importlib.util

import pytest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "tools" / "sensitive_scan.py"


def _load_scanner():
    spec = importlib.util.spec_from_file_location("sensitive_scan", SCANNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def scan(monkeypatch):
    if not (ROOT / ".git").exists():
        pytest.skip("非 git 检出（无 .git 目录），脱敏检查跳过")
    monkeypatch.chdir(ROOT)                 # 扫描器按相对路径读跟踪文件与 git 元数据
    return _load_scanner()


def test_scan_selftest_positive_and_negative_controls(scan):
    ok, report = scan.selftest()
    assert ok, "\n".join(report)


def test_tracked_files_have_no_sensitive_content(scan):
    findings, _ = scan.scan_tracked()
    assert findings == [], findings


def test_history_and_commit_messages_are_clean(scan):
    assert scan.scan_history()[0] == []
    assert scan.scan_messages()[0] == []


def test_binary_samples_have_no_sensitive_metadata(scan):
    """二进制样例本体：PDF Info 元数据域（构建机路径/真实姓名邮箱的藏点）
    与 OFD·ZIP 逐条目解压内容——文本扫描对二进制是盲区，必须单独扫。"""
    findings, _ = scan.scan_binaries()
    assert findings == [], findings


def test_commit_metadata_has_no_personal_email(scan):
    """提交作者/提交者邮箱只允许 GitHub 系统地址（含 bot/merge），不得出现真实个人邮箱。"""
    findings, _ = scan.scan_metadata()
    assert findings == [], findings
