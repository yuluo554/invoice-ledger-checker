"""法规知识库守门（M7）：data/knowledge/*.json 的结构契约 + 规则依据一致性。

三层断言：
1. 结构层——三份 json 存在、entries 非空、每条有非空 article_no + quote；
   verification.status 只取精确枚举值（不含后缀）；每份挂复核锚
   reviewed_at / next_review（合法 ISO 日期）/ review_interval。
2. 一致性层——8 条内置规则的 basis.knowledge_ref 都能解析到某份 json 的某条
   entry，且代码里字面书写的 quote 与 json 的 quote **逐字相等**
   （字面 quote 是发布形态：知识库不在 wheel 里，运行期不读 json）。
3. 时效层——任一 next_review 早于今天：打印警告但**不 fail**（否则 2027 年
   这个测试会自己变红，把"该复核了"变成"构建挂了"）。
"""

import datetime
import json
import re
from pathlib import Path

import pytest

from invoice_ledger_checker.rules import DetectionEngine, register_builtin

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"
STATUS_VALUES = ("已核对", "待核对")
_REF_RE = re.compile(r"^(?P<file>.+?\.json)#(?P<entry>.+)$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _knowledge_files():
    files = sorted(KNOWLEDGE_DIR.glob("*.json"))
    assert files, "data/knowledge/ 应至少有一份法规 json"
    return files


def _load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def knowledge():
    """{文件名: 解析结果}（模块级缓存，避免每用例重读三份 json）。"""
    return {path.name: _load(path) for path in _knowledge_files()}


@pytest.fixture(scope="module")
def rule_bases():
    engine = DetectionEngine()
    register_builtin(engine)
    return {rule.rule_id: rule for rule in engine._rules}


# ---------------------------------------------------------------- 结构层


def test_each_file_has_entries_with_article_and_quote(knowledge):
    for name, payload in knowledge.items():
        entries = payload.get("entries")
        assert isinstance(entries, list) and entries, "%s 的 entries 为空" % name
        for entry in entries:
            assert entry.get("id"), "%s 有 entry 缺 id" % name
            assert str(entry.get("article_no") or "").strip(), \
                "%s#%s 缺 article_no" % (name, entry.get("id"))
            assert str(entry.get("quote") or "").strip(), \
                "%s#%s 缺 quote" % (name, entry.get("id"))


def test_verification_status_is_exact_enum(knowledge):
    """status 只取精确值（带后缀的叙述会让任何 status=='已核对' 过滤漏掉该文件）。"""
    for name, payload in knowledge.items():
        verification = payload.get("verification")
        assert isinstance(verification, dict), "%s 缺 verification 段" % name
        status = verification.get("status")
        assert status in STATUS_VALUES, \
            "%s 的 verification.status = %r，须为精确值 %s" % (name, status, STATUS_VALUES)
        # 叙述性说明只许放在 status_note（不许混进 status）
        assert "（" not in str(status), \
            "%s 的 status 掺入了叙述（应移到 status_note）: %r" % (name, status)


def test_verification_review_anchor_present_and_valid(knowledge):
    for name, payload in knowledge.items():
        verification = payload["verification"]
        reviewed_at = verification.get("reviewed_at")
        next_review = verification.get("next_review")
        assert reviewed_at, "%s 缺 reviewed_at" % name
        assert next_review, "%s 缺 next_review" % name
        for label, value in (("reviewed_at", reviewed_at), ("next_review", next_review)):
            assert _ISO_DATE_RE.match(str(value)), \
                "%s 的 %s = %r 不是 ISO 日期（YYYY-MM-DD）" % (name, label, value)
            datetime.date.fromisoformat(str(value))  # 非法日期在此抛 ValueError
        assert reviewed_at <= next_review, \
            "%s 的 next_review 早于 reviewed_at" % name
        assert verification.get("review_interval"), "%s 缺 review_interval" % name


def test_verification_shape_is_uniform(knowledge):
    """三份 json 的 verification 键集一致（防止结构再次漂移：D6）。"""
    key_sets = {name: set(payload["verification"]) for name, payload in knowledge.items()}
    baseline_name = sorted(key_sets)[0]
    baseline = key_sets[baseline_name]
    for name, keys in key_sets.items():
        assert keys == baseline, (
            "%s 的 verification 键集与 %s 不一致：多 %s / 少 %s"
            % (name, baseline_name, sorted(keys - baseline), sorted(baseline - keys)))


def test_review_overdue_warns_but_does_not_fail(knowledge):
    """复核逾期只提示不判红（避免 2027 年这个测试自己变红）。"""
    today = datetime.date.today()
    overdue = []
    for name, payload in knowledge.items():
        next_review = payload["verification"]["next_review"]
        due = datetime.date.fromisoformat(str(next_review))
        if due < today:
            overdue.append("%s（next_review=%s，已逾期 %d 天）"
                           % (name, next_review, (today - due).days))
    if overdue:
        import warnings

        warnings.warn("复核逾期：%s —— 请补核法规原文并更新 reviewed_at/next_review"
                      % "；".join(overdue), stacklevel=2)


# ---------------------------------------------------------------- 一致性层


def test_every_rule_has_basis_with_knowledge_ref(rule_bases):
    assert len(rule_bases) == 8, "内置规则应为 8 条（实际 %d）" % len(rule_bases)
    for rule_id, rule in rule_bases.items():
        basis = rule.basis
        assert basis, "规则 %s 缺 basis" % rule_id
        for key in ("regulation", "regulation_short", "article", "knowledge_ref", "quote"):
            assert str(basis.get(key) or "").strip(), \
                "规则 %s 的 basis 缺 %s" % (rule_id, key)


def test_rule_knowledge_ref_resolves_to_entry(rule_bases, knowledge):
    """每条规则的 knowledge_ref 都能解析到某份 json 的某条 entry。"""
    for rule_id, rule in rule_bases.items():
        ref = rule.basis["knowledge_ref"]
        match = _REF_RE.match(ref)
        assert match, "规则 %s 的 knowledge_ref 形态非法: %r" % (rule_id, ref)
        file_name, entry_id = match.group("file"), match.group("entry")
        assert file_name in knowledge, "规则 %s 引用了不存在的知识库文件: %s" % (
            rule_id, file_name)
        entry_ids = {entry.get("id") for entry in knowledge[file_name]["entries"]}
        assert entry_id in entry_ids, "规则 %s 引用了 %s 中不存在的条目: %s" % (
            rule_id, file_name, entry_id)


def test_rule_article_matches_entry_article(rule_bases, knowledge):
    for rule_id, rule in rule_bases.items():
        file_name, entry_id = _REF_RE.match(rule.basis["knowledge_ref"]).groups()
        entry = next(e for e in knowledge[file_name]["entries"]
                     if e.get("id") == entry_id)
        assert rule.basis["article"] == entry["article_no"], (
            "规则 %s 的 article=%r 与 %s#%s 的 article_no=%r 不一致"
            % (rule_id, rule.basis["article"], file_name, entry_id, entry["article_no"]))


def test_rule_quote_matches_knowledge_quote_verbatim(rule_bases, knowledge):
    """代码里的字面 quote 必须与 json 的 quote 逐字相等（单一事实源）。"""
    for rule_id, rule in rule_bases.items():
        file_name, entry_id = _REF_RE.match(rule.basis["knowledge_ref"]).groups()
        entry = next(e for e in knowledge[file_name]["entries"]
                     if e.get("id") == entry_id)
        assert rule.basis["quote"] == entry["quote"], (
            "规则 %s 的 quote 与 %s#%s 不一致（须逐字复制）\n代码: %r\njson: %r"
            % (rule_id, file_name, entry_id,
               rule.basis["quote"], entry["quote"]))


def test_heuristic_rules_carry_note(rule_bases):
    """弱关联三规则必须带 note 如实披露（法规无直接条款，非免责话术）。"""
    for rule_id in ("R-SEQ-01", "R-TIME-01", "R-TIME-02"):
        note = rule_bases[rule_id].basis.get("note") or ""
        assert note.startswith("工程口径"), \
            "规则 %s 缺工程口径 note（弱关联须如实披露）" % rule_id


def test_strong_rules_have_no_heuristic_note(rule_bases):
    """强关联规则不许挂 note（避免把有直接条款的规则也降级成启发式）。"""
    for rule_id in ("R-ARITH-01", "R-ARITH-02", "R-DUP-01", "R-DUP-02", "R-DUP-03"):
        assert not rule_bases[rule_id].basis.get("note"), \
            "规则 %s 是强关联，不应挂 note" % rule_id


def test_findings_carry_rule_basis(rule_bases):
    """引擎透传：任一规则产出的 finding 都带该规则的 basis（判定逻辑不变）。"""
    from invoice_ledger_checker.models import InvoiceCard, LineItem

    def card(number="25910000000000123456", amount="1000.00", tax="130.00",
             total="1130.00", cn="壹仟壹佰叁拾元整"):
        return InvoiceCard(
            invoice_number=number,
            invoice_type="数电普票",
            issue_date="2026-01-05",
            seller_name="云图商贸有限公司",
            seller_tax_id="91330100FAKE000001",
            items=[LineItem(name="会议服务费", amount="1000.00",
                            tax_rate="0.13", tax_amount="130.00")],
            amount=amount,
            tax_amount=tax,
            total_with_tax=total,
            total_with_tax_cn=cn,
            batch_id="batch_01",
        )

    engine = DetectionEngine()
    register_builtin(engine)
    findings = engine.run([card(total="2180.00", cn="贰仟壹佰捌拾元整")])
    assert findings, "构造的算术错卡应产出 finding"
    for finding in findings:
        assert finding.basis, "finding %s 未携带 basis" % finding.rule_id
        assert finding.basis == rule_bases[finding.rule_id].basis
        assert finding.to_dict()["basis"] == rule_bases[finding.rule_id].basis
