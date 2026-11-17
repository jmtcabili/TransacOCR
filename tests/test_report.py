import csv
import io
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from bot import storage
from bot.domain import Parsed
from bot.report import build_report, render_csv, render_message

TZ = ZoneInfo("Asia/Manila")
DAY = "2026-05-20"


@pytest.fixture
def conn(tmp_path):
    return storage.connect(str(tmp_path / "t.db"))


def add(conn, n, chat=-1, received="2026-05-20T10:00:00+00:00", name="Juan, Jr. \"JJ\"", **p):
    rid = storage.insert_receipt(conn, update_id=n, chat_id=chat, user_id=1, message_id=n, submitter_name=name,
                                 img=dict(source="photo", file_id="f", file_unique_id=f"u{n}"))
    conn.execute("UPDATE receipts SET received_at=? WHERE id=?", (received, rid))
    base = dict(provider="GCash", amount=Decimal("300.00"), printed_date=DAY, printed_time="10:00",
                reference_number=f"R{n}", recipient_name="JO****A C.")
    storage.record_result(conn, rid, chat, Parsed(**{**base, **p}))
    return rid


def test_total_and_counts_by_provider(conn):
    add(conn, 1); add(conn, 2); add(conn, 3, provider="BPI", amount=Decimal("1000.50"))
    rep = build_report(conn, -1, DAY, TZ)
    assert (rep.total, rep.count, dict(rep.per_provider)) == (Decimal("1600.50"), 3, {"GCash": 2, "BPI": 1})
    assert render_message(rep) == "\n".join([
        "📊 End-of-day report · 2026-05-20", "💵 Total: 1,600.50 pesos", "🧾 Total transactions: 3", "- 2 GCash", "- 1 BPI"])


def test_groups_by_printed_date_not_received_date(conn):
    add(conn, 1, printed_date="2026-05-19", received="2026-05-20T10:00:00+00:00")
    add(conn, 2, printed_date=DAY, received="2026-05-21T10:00:00+00:00")
    assert [r["reference_number"] for r in build_report(conn, -1, DAY, TZ).transactions] == ["R2"]


def test_other_chats_never_appear(conn):
    add(conn, 1, chat=-1); add(conn, 2, chat=-2)
    rep = build_report(conn, -1, DAY, TZ)
    assert rep.count == 1 and rep.transactions[0]["reference_number"] == "R1"


def test_needs_review_is_listed_not_counted(conn):
    add(conn, 1)
    add(conn, 2, reference_number=None)                   # dated, no reference
    add(conn, 3, txn_status="pending")
    add(conn, 4, printed_date=None, received="2026-05-20T01:00:00+00:00")   # undated: placed by Manila received day
    add(conn, 5, printed_date=None, received="2026-05-19T10:00:00+00:00")   # a different day
    rep = build_report(conn, -1, DAY, TZ)
    assert rep.count == 1 and rep.total == Decimal("300.00") and len(rep.review) == 3
    text = render_message(rep)
    assert "⚠️ Needs review (3):" in text and "reference number not read" in text and "transaction not successful" in text


def test_duplicates_are_not_counted(conn):
    add(conn, 1, reference_number="SAME"); add(conn, 2, reference_number="SAME")
    assert build_report(conn, -1, DAY, TZ).count == 1


def test_zero_transactions(conn):
    rep = build_report(conn, -1, DAY, TZ)
    assert render_message(rep).endswith("No transactions today.")
    assert render_message(rep, is_today=False).endswith("No transactions on 2026-05-20.")


def test_csv_round_trips_commas_and_quotes(conn):
    add(conn, 1); add(conn, 2, reference_number=None)
    raw = render_csv(build_report(conn, -1, DAY, TZ))
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert [r["status"] for r in rows] == ["clean", "needs_review"]
    assert rows[0]["submitter"] == 'Juan, Jr. "JJ"' and rows[0]["reference_number"] == "R1" and rows[0]["amount"] == "300.00"


def test_review_list_is_capped(conn):
    for n in range(1, 21):
        add(conn, n, reference_number=None)
    text = render_message(build_report(conn, -1, DAY, TZ))
    assert text.count("\n- ") == 15 and "…and 5 more (see the CSV)." in text
