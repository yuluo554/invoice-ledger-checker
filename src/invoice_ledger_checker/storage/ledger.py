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
        """登记批次；已存在时保持原记录（重跑 check 幂等，不覆盖首次导入时间）。"""
        self.conn.execute(
            "INSERT OR IGNORE INTO batches (batch_id, imported_at, source_desc,"
            " file_count, log_json) VALUES (?, ?, ?, ?, ?)",
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

    def existing_numbers(self) -> set:
        """台账既有发票号码全集（check 命令入库前查询，R-DUP-01 持久判重输入）。"""
        return {row[0] for row in self.conn.execute("SELECT invoice_number FROM invoices")}

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
            " batch_id, status, created_at FROM findings ORDER BY created_at, finding_id"
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
                "created_at": r[8],
            }
            for r in rows
        ]

    def set_finding_status(self, finding_id: str, status: str) -> bool:
        """人工复核动作（M5 GUI）：open/confirmed/dismissed。"""
        if status not in ("open", "confirmed", "dismissed"):
            raise ValueError("非法 finding 状态: %r" % status)
        cur = self.conn.execute(
            "UPDATE findings SET status = ? WHERE finding_id = ?",
            (status, finding_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ---- 台账查询/筛选/CRUD（M5 GUI 数据源；FR-07/08） ----

    @staticmethod
    def _invoice_filters(month=None, seller_like=None, invoice_type=None,
                         amount_min=None, amount_max=None):
        """参数化 WHERE 组装（plan/04 §4：维度固定，无需 ORM）。"""
        clauses, params = [], []
        if month:
            clauses.append("substr(issue_date, 1, 7) = ?")
            params.append(str(month))
        if seller_like:
            clauses.append("(seller_name LIKE ? OR seller_tax_id LIKE ?)")
            like = "%" + str(seller_like) + "%"
            params.extend([like, like])
        if invoice_type:
            clauses.append("invoice_type = ?")
            params.append(str(invoice_type))
        if amount_min not in (None, ""):
            clauses.append("CAST(total_with_tax AS REAL) >= ?")
            params.append(float(amount_min))
        if amount_max not in (None, ""):
            clauses.append("CAST(total_with_tax AS REAL) <= ?")
            params.append(float(amount_max))
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    _INVOICE_PAGE_SQL = (
        "SELECT invoice_number, invoice_type, issue_date, buyer_name, seller_name,"
        " amount, tax_amount, total_with_tax, batch_id FROM invoices"
    )

    def query_invoices(self, month=None, seller_like=None, invoice_type=None,
                       amount_min=None, amount_max=None,
                       page: int = 1, page_size: int = 50):
        """多维筛选 + 分页（排序=开票日期,号码，稳定序）。返回 (rows, total)。"""
        where_sql, params = self._invoice_filters(
            month, seller_like, invoice_type, amount_min, amount_max)
        total = self.conn.execute(
            "SELECT COUNT(*) FROM invoices" + where_sql, params).fetchone()[0]
        rows = self.conn.execute(
            self._INVOICE_PAGE_SQL + where_sql
            + " ORDER BY issue_date, invoice_number LIMIT ? OFFSET ?",
            params + [int(page_size), (int(page) - 1) * int(page_size)],
        ).fetchall()
        keys = ("invoice_number", "invoice_type", "issue_date", "buyer_name",
                "seller_name", "amount", "tax_amount", "total_with_tax", "batch_id")
        return [dict(zip(keys, r)) for r in rows], int(total)

    def distinct_months(self) -> List[str]:
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT substr(issue_date, 1, 7) AS m FROM invoices"
            " ORDER BY m") if r[0]]

    def distinct_invoice_types(self) -> List[str]:
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT invoice_type FROM invoices ORDER BY invoice_type")
            if r[0]]

    def get_invoice(self, invoice_number: str) -> Optional[InvoiceCard]:
        row = self.conn.execute(
            "SELECT card_json FROM invoices WHERE invoice_number = ?",
            (invoice_number,),
        ).fetchone()
        if row is None:
            return None
        return InvoiceCard.from_dict(json.loads(row[0]))

    def delete_invoice(self, invoice_number: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM invoices WHERE invoice_number = ?", (invoice_number,))
        self.conn.commit()
        return cur.rowcount > 0

    def update_invoice_fields(self, invoice_number: str,
                              buyer_name: Optional[str] = None,
                              seller_name: Optional[str] = None,
                              remark: Optional[str] = None) -> bool:
        """台账维护编辑（FR-08）：仅联系人字段可改，金额/号码/日期只读
        （财务字段改动破坏对账链）；card_json 同步重写保持一致。"""
        card = self.get_invoice(invoice_number)
        if card is None:
            return False
        if buyer_name is not None:
            card.buyer_name = buyer_name
        if seller_name is not None:
            card.seller_name = seller_name
        if remark is not None:
            card.remark = remark
        cur = self.conn.execute(
            "UPDATE invoices SET buyer_name = ?, seller_name = ?, remark = ?,"
            " card_json = ? WHERE invoice_number = ?",
            (card.buyer_name, card.seller_name, card.remark,
             json.dumps(card.to_dict(), ensure_ascii=False), invoice_number),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ---- 看板聚合（M5 GUI；显示层 SUM 用 REAL 近似，账面值仍以 Decimal 文本为准） ----

    def monthly_stats(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT substr(issue_date, 1, 7) AS m, COUNT(*),"
            " SUM(CAST(total_with_tax AS REAL)) FROM invoices"
            " WHERE issue_date != '' GROUP BY m ORDER BY m"
        ).fetchall()
        return [{"month": r[0], "count": int(r[1]), "total": float(r[2] or 0)}
                for r in rows]

    def top_sellers(self, n: int = 10) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT seller_name, seller_tax_id, COUNT(*),"
            " SUM(CAST(total_with_tax AS REAL)) FROM invoices"
            " GROUP BY seller_tax_id, seller_name"
            " ORDER BY COUNT(*) DESC, seller_name LIMIT ?",
            (int(n),),
        ).fetchall()
        return [{"seller_name": r[0] or "(未知)", "seller_tax_id": r[1],
                 "count": int(r[2]), "total": float(r[3] or 0)}
                for r in rows]

    def type_distribution(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT invoice_type, COUNT(*) FROM invoices"
            " GROUP BY invoice_type ORDER BY COUNT(*) DESC"
        ).fetchall()
        return [{"invoice_type": r[0], "count": int(r[1])} for r in rows]


def _now_iso() -> str:
    import datetime

    return datetime.datetime.now().replace(microsecond=0).isoformat()
