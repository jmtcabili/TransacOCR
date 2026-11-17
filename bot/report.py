"""End-of-day report: PHP total and per-Provider counts for one printed date, Needs-review items, CSV."""
import csv
import io
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from bot.replies import DASH, REASON_TEXT, money

CSV_COLUMNS = ["reference_number", "provider", "amount", "date", "time", "recipient", "status", "submitter",
               "received_at", "review_reasons"]
MAX_REVIEW_LINES = 15


@dataclass
class Report:
    day: str
    total: Decimal
    count: int
    per_provider: Counter
    transactions: list     # counted rows (outcome clean, printed on `day`)
    review: list           # Needs-review rows, listed but not counted


def build_report(conn, chat_id: int, day: str, tz: ZoneInfo) -> Report:
    txns = conn.execute(
        "SELECT * FROM receipts WHERE chat_id=? AND outcome='clean' AND printed_date=? ORDER BY printed_time, id",
        (chat_id, day)).fetchall()
    # Needs-review rows with a printed date belong to that day. Undated ones can't be placed on a day,
    # so they are listed on the day the bot received them (Manila time).
    review = [r for r in conn.execute(
        "SELECT * FROM receipts WHERE chat_id=? AND outcome='needs_review' AND (printed_date=? OR printed_date IS NULL) ORDER BY id",
        (chat_id, day)) if r["printed_date"] == day or _received_day(r["received_at"], tz) == day]
    return Report(day, sum((Decimal(r["amount"]) for r in txns), Decimal("0")), len(txns),
                  Counter(r["provider"] for r in txns), txns, review)


def _received_day(received_at: str, tz: ZoneInfo) -> str:
    return datetime.fromisoformat(received_at).astimezone(tz).date().isoformat()


def render_message(rep: Report, is_today: bool = True) -> str:
    lines = [f"📊 End-of-day report · {rep.day}"]
    if rep.count:
        lines += [f"💵 Total: {rep.total:,.2f} pesos", f"🧾 Total transactions: {rep.count}"]
        lines += [f"- {n} {prov}" for prov, n in sorted(rep.per_provider.items(), key=lambda kv: (-kv[1], kv[0]))]
    else:
        lines.append("No transactions today." if is_today else f"No transactions on {rep.day}.")
    if rep.review:
        lines.append(f"⚠️ Needs review ({len(rep.review)}):")
        for r in rep.review[:MAX_REVIEW_LINES]:
            why = ", ".join(REASON_TEXT.get(x, x) for x in (r["review_reasons"] or "").split(",") if x)
            amount = money(Decimal(r["amount"])) if r["amount"] else DASH
            lines.append(f"- {r['provider'] or 'unread'} · ref {r['reference_number'] or DASH} · {amount} · {why}")
        if len(rep.review) > MAX_REVIEW_LINES:
            lines.append(f"…and {len(rep.review) - MAX_REVIEW_LINES} more (see the CSV).")
    return "\n".join(lines)


def render_csv(rep: Report) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_COLUMNS)
    for status, rows in (("clean", rep.transactions), ("needs_review", rep.review)):
        for r in rows:
            w.writerow([r["reference_number"], r["provider"], r["amount"], r["printed_date"], r["printed_time"],
                        " ".join(x for x in (r["recipient_name"], r["recipient_account"]) if x), status,
                        r["submitter_name"] or r["user_id"], r["received_at"], r["review_reasons"]])
    return out.getvalue().encode("utf-8-sig")   # BOM so Excel opens it as UTF-8
