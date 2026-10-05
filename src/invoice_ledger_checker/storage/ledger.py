"""SQLite 本地台账（M3 扩展 GUI 侧；schema 契约权威出处 plan/04 §4）。

- 金额全存 Decimal 文本（str），比较在应用层做，规避 SQLite 浮点差异；
- invoices 主键即 R-DUP-01 实现基础：重复导入触发 IntegrityError →
  add_invoice 返回 False（不 UPSERT 覆盖——重复导入本身就是异常信号）；
- card_json 存 InvoiceCard 全量序列化，iter_cards 可完整还原。
"""

import json
import sqlite3
from typing import Any, Dict, Iterator, List, Optional

from ..models import InvoiceCard

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id    TEXT PRIMARY KEY,
    imported_at TEXT NOT NULL,
    source_desc TEXT DEFAULT '',
    file_count  INTEGER DEFAULT 0,
    log_json    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_number TEXT PRIMARY KEY,
    invoice_type TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    buyer_name TEXT DEFAULT '', buyer_tax_id TEXT DEFAULT '',
    seller_name TEXT DEFAULT '', seller_tax_id TEXT DEFAULT '',
    amount TEXT NOT NULL, tax_amount TEXT NOT NULL, total_with_tax TEXT NOT NULL,
    total_with_tax_cn TEXT DEFAULT '', remark TEXT DEFAULT '',
    items_json TEXT NOT NULL,
    card_json TEXT NOT NULL,
    batch_id TEXT NOT NULL REFERENCES batches(batch_id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('error','suspicious','review')),
    invoice_numbers TEXT NOT NULL,
    message TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    batch_id TEXT,
    status TEXT DEFAULT 'open',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inv_seller_date ON invoices(seller_tax_id, issue_date);
CREATE INDEX IF NOT EXISTS idx_inv_batch ON invoices(batch_id);
CREATE INDEX IF NOT EXISTS idx_find_rule ON findings(rule_id, level);
"""

_FINDING_REQUIRED = ("finding_id", "rule_id", "level", "invoice_numbers", "message")


class Ledger:
    """单文件 SQLite 台账；path 默认内存库（演示/测试用）。"""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        self.conn.close()

    # ---- 批次 ----

    def create_batch(self, batch_id: str, source_desc: str = "", file_count: int = 0) -> str:
        self.conn.execute(
            "INSERT INTO batches (batch_id, imported_at, source_desc, file_count, log_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (batch_id, _now_iso(), source_desc, file_count, ""),
        )
        self.conn.commit()
        return batch_id

    # ---- 发票 ----

    def add_invoice(self, card: InvoiceCard, batch_id: str) -> bool:
        """入库；主键冲突（同号已存在）返回 False——重复导入是异常信号，不覆盖。"""
        card.batch_id = batch_id
        try:
            self.conn.execute(
                "INSERT INTO invoices (invoice_number, invoice_type, issue_date,"
                " buyer_name, buyer_tax_id, seller_name, seller_tax_id,"
                " amount, tax_amount, total_with_tax, total_with_tax_cn, remark,"
                " items_json, card_json, batch_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card.invoice_number,
                    card.invoice_type,
                    card.issue_date,
                    card.buyer_name,
                    card.buyer_tax_id,
                    card.seller_name,
                    card.seller_tax_id,
                    card.amount,
                    card.tax_amount,
                    card.total_with_tax,
                    card.total_with_tax_cn,
                    card.remark,
                    json.dumps([item.__dict__ for item in card.items], ensure_ascii=False),
                    json.dumps(card.to_dict(), ensure_ascii=False),
                    batch_id,
                    _now_iso(),
                ),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False
        self.conn.commit()
        return True

    def count_invoices(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0])

    def iter_cards(self) -> Iterator[InvoiceCard]:
        for (card_json,) in self.conn.execute("SELECT card_json FROM invoices"):
            yield InvoiceCard.from_dict(json.loads(card_json))

    # ---- 异常记录 ----

    def add_finding(self, finding: Dict[str, Any], batch_id: Optional[str] = None) -> bool:
        missing = [k for k in _FINDING_REQUIRED if not finding.get(k)]
        if missing:
            raise ValueError("finding 缺必填字段: %s" % ",".join(missing))
        try:
            self.conn.execute(
                "INSERT INTO findings (finding_id, rule_id, level, invoice_numbers,"
                " message, evidence_json, batch_id, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
                (
                    finding["finding_id"],
                    finding["rule_id"],
                    finding["level"],
                    json.dumps(finding["invoice_numbers"], ensure_ascii=False),
                    finding["message"],
                    json.dumps(finding.get("evidence", {}), ensure_ascii=False),
                    batch_id,
                    _now_iso(),
                ),
            )
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False
        self.conn.commit()
        return True

    def list_findings(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT finding_id, rule_id, level, invoice_numbers, message, evidence_json,"
            " batch_id, status FROM findings ORDER BY created_at, finding_id"
        ).fetchall()
        return [
            {
                "finding_id": r[0],
                "rule_id": r[1],
                "level": r[2],
                "invoice_numbers": json.loads(r[3]),
                "message": r[4],
                "evidence": json.loads(r[5]),
                "batch_id": r[6],
                "status": r[7],
            }
            for r in rows
        ]


def _now_iso() -> str:
    import datetime

    return datetime.datetime.now().replace(microsecond=0).isoformat()
