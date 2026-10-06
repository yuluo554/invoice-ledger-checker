# -*- coding: utf-8 -*-
"""CI workflow 守门（M6 发布期实测暴露的问题固化）。

发布期实录：`.github/workflows/ci.yml` 中一个 step 名写成**不带引号的纯量**且内含
「冒号+空格」（形如 `Run full tests (GUI offscreen: QT_QPA_PLATFORM ...)`），
YAML 解析直接失败 → GitHub 拒绝整份 workflow：**run 0 秒失败、jobs=0**，
连"红"都看不到。此前仓库无 remote、workflow 从未执行，故该缺陷潜伏到发布才暴露。

守门方式：用 pyyaml 解析全部 workflow 文件并断言 job 结构（pyyaml 已入 dev extras，
CI 各作业都装 dev → 本测试真跑，不静默跳过）。
"""

import yaml

from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _workflow_files():
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert files, "仓库应至少有一份 CI workflow"
    return files


def test_workflow_files_are_valid_yaml_with_jobs():
    """可解析 + 至少一个 job，且每个 job 声明了 runs-on / steps（防 0 秒空跑）。"""
    for path in _workflow_files():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "%s 顶层应为映射" % path.name
        jobs = data.get("jobs")
        assert isinstance(jobs, dict) and jobs, \
            "%s 未声明任何 job（GitHub 会 0 秒失败）" % path.name
        for name, job in jobs.items():
            assert isinstance(job, dict), "%s 的 job %s 应为映射" % (path.name, name)
            assert job.get("runs-on"), "%s 的 job %s 缺 runs-on" % (path.name, name)
            assert job.get("steps"), "%s 的 job %s 缺 steps" % (path.name, name)


def test_ci_workflow_declares_expected_jobs():
    """CI 分工固化：test（三矩阵）/ desktop / benchmark。

    改 CI 作业分工或矩阵规模须同步本测试 + README 限制节（既定口径：改装机清单
    会改变 skip 计数口径）。
    """
    data = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    assert set(data["jobs"]) == {"test", "desktop", "benchmark"}
    matrix = data["jobs"]["test"]["strategy"]["matrix"]["include"]
    assert len(matrix) == 3, "test 作业应为三矩阵（win-3.8 / win-3.12 / ubuntu-3.12）"
