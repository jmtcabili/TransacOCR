"""SQLite storage for Receipts. Every query that reads Transactions is scoped by chat_id."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

from bot.domain import Parsed, dedupe_key, needs_review

# Pipeline state lives in `status` (received -> downloaded -> done | error).
# What the Receipt turned out to be lives in `outcome` (clean | needs_review | duplicate).
BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts(
    id                  INTEGER PRIMARY KEY,
    update_id           INTEGER NOT NULL UNIQUE,
    chat_id             INTEGER NOT NULL,
    user_id             INTEGER,
    message_id          INTEGER NOT NULL,
    file_unique_id      TEXT NOT NULL,
    file_id             TEXT NOT NULL,
    original_name       TEXT,
    mime_type           TEXT,
    file_size           INTEGER,
    width               INTEGER,
    height              INTEGER,
    source              TEXT NOT NULL,
    stored_path         TEXT,
    sha256              TEXT,
    status              TEXT NOT NULL DEFAULT 'received',
    received_at         TEXT NOT NULL
)"""

NEW_COLUMNS = {
    "submitter_name": "TEXT",
    "outcome": "TEXT",
    "review_reasons": "TEXT",
    "duplicate_of": "INTEGER",
    "provider": "TEXT",
    "txn_status": "TEXT",
    "transaction_type": "TEXT",
    "amount": "TEXT",
    "fee": "TEXT",
    "total": "TEXT",
    "currency": "TEXT",
    "printed_date": "TEXT",
    "printed_time": "TEXT",
    "reference_number": "TEXT",
    "sender_name": "TEXT",
    "recipient_name": "TEXT",
    "recipient_account": "TEXT",
}


def connect(db_path: str) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)   # SQLite won't create the folder
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(BASE_SCHEMA)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(receipts)")}
    for col, typ in NEW_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE receipts ADD COLUMN {col} {typ}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_status ON receipts(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_receipts_day ON receipts(chat_id, printed_date)")
    # One Transaction per (chat, provider, reference, printed date); duplicates are kept as rows but excluded.
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_transaction
        ON receipts(chat_id, provider, reference_number, printed_date)
        WHERE outcome IN ('clean', 'needs_review')
          AND reference_number IS NOT NULL AND printed_date IS NOT NULL""")
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_receipt(conn, *, update_id, chat_id, user_id, message_id, img, submitter_name=None) -> int | None:
    """Insert one row per Telegram update. Returns the row id, or None if update_id was already stored."""
    try:
        cur = conn.execute(
            """INSERT INTO receipts
               (update_id, chat_id, user_id, submitter_name, message_id, file_unique_id, file_id,
                original_name, mime_type, file_size, width, height, source, received_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (update_id, chat_id, user_id, submitter_name, message_id, img["file_unique_id"], img["file_id"],
             img.get("original_name"), img.get("mime_type"), img.get("file_size"),
             img.get("width"), img.get("height"), img["source"], _now()),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        conn.rollback()
        return None


def get(conn, receipt_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM receipts WHERE id=?", (receipt_id,)).fetchone()


def mark_downloaded(conn, receipt_id: int, stored_path: str, sha256: str) -> None:
    conn.execute("UPDATE receipts SET stored_path=?, sha256=?, status='downloaded' WHERE id=? AND status='received'",
                 (stored_path, sha256, receipt_id))
    conn.commit()


def find_duplicate(conn, chat_id: int, p: Parsed, exclude_id: int | None = None) -> int | None:
    if dedupe_key(chat_id, p) is None:
        return None
    row = conn.execute(
        """SELECT id FROM receipts WHERE chat_id=? AND provider=? AND reference_number=? AND printed_date=?
           AND outcome IN ('clean','needs_review') AND id != ?""",
        (chat_id, p.provider, p.reference_number, p.printed_date, exclude_id or -1)).fetchone()
    return row["id"] if row else None


def record_result(conn, receipt_id: int, chat_id: int, p: Parsed) -> tuple[str, list[str], int | None]:
    """Store a parse result. Returns (outcome, review_reasons, duplicate_of)."""
    dup = find_duplicate(conn, chat_id, p, exclude_id=receipt_id)
    reasons = needs_review(p)
    outcome = "duplicate" if dup else ("needs_review" if reasons else "clean")
    conn.execute(
        """UPDATE receipts SET status='done', outcome=?, review_reasons=?, duplicate_of=?, provider=?, txn_status=?,
           transaction_type=?, amount=?, fee=?, total=?, currency=?, printed_date=?, printed_time=?,
           reference_number=?, sender_name=?, recipient_name=?, recipient_account=? WHERE id=?""",
        (outcome, ",".join(reasons), dup, p.provider, p.txn_status, p.transaction_type,
         *(None if v is None else str(v) for v in (p.amount, p.fee, p.total)),
         p.currency, p.printed_date, p.printed_time, p.reference_number, p.sender_name,
         p.recipient_name, p.recipient_account, receipt_id))
    conn.commit()
    return outcome, reasons, dup


def record_error(conn, receipt_id: int, reason: str = "ocr_error") -> None:
    conn.execute("UPDATE receipts SET status='error', outcome='needs_review', review_reasons=? WHERE id=?",
                 (reason, receipt_id))
    conn.commit()


def money(v) -> Decimal | None:
    return None if v is None else Decimal(v)
