import sqlite3
from decimal import Decimal

import pytest

from bot import storage
from bot.domain import Parsed

IMG = dict(source="photo", file_id="f", file_unique_id="u", mime_type="image/jpeg")


@pytest.fixture
def conn(tmp_path):
    return storage.connect(str(tmp_path / "t.db"))


def add(conn, update_id, chat_id=-1):
    return storage.insert_receipt(conn, update_id=update_id, chat_id=chat_id, user_id=1, message_id=update_id, img=IMG)


def parsed(**kw):
    base = dict(provider="GCash", amount=Decimal("300.00"), printed_date="2026-05-20", reference_number="R1")
    return Parsed(**{**base, **kw})


def test_redelivered_update_is_ignored(conn):
    assert add(conn, 10) is not None
    assert add(conn, 10) is None
    assert conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1


def test_clean_then_duplicate(conn):
    a, b = add(conn, 1), add(conn, 2)
    assert storage.record_result(conn, a, -1, parsed()) == ("clean", [], None)
    assert storage.record_result(conn, b, -1, parsed()) == ("duplicate", [], a)


def test_same_transaction_in_another_chat_is_not_duplicate(conn):
    a, b = add(conn, 1, -1), add(conn, 2, -2)
    storage.record_result(conn, a, -1, parsed())
    assert storage.record_result(conn, b, -2, parsed())[0] == "clean"


def test_null_key_never_collides(conn):
    a, b = add(conn, 1), add(conn, 2)
    assert storage.record_result(conn, a, -1, parsed(reference_number=None))[0] == "needs_review"
    assert storage.record_result(conn, b, -1, parsed(reference_number=None))[0] == "needs_review"


def test_unique_index_backs_up_the_check(conn):
    a, b = add(conn, 1), add(conn, 2)
    storage.record_result(conn, a, -1, parsed())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE receipts SET outcome='clean', provider='GCash', reference_number='R1', "
                     "printed_date='2026-05-20' WHERE id=?", (b,))


def test_record_error_marks_needs_review(conn):
    a = add(conn, 1)
    storage.record_error(conn, a)
    row = storage.get(conn, a)
    assert (row["status"], row["outcome"], row["review_reasons"]) == ("error", "needs_review", "ocr_error")


def test_existing_db_is_migrated_without_losing_rows(tmp_path):
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.execute(storage.BASE_SCHEMA)
    old.execute("INSERT INTO receipts(update_id,chat_id,message_id,file_unique_id,file_id,source,received_at)"
                " VALUES (1,-1,1,'u','f','photo','2026-01-01')")
    old.commit(); old.close()
    c = storage.connect(path)
    assert c.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1
    assert "reference_number" in {r["name"] for r in c.execute("PRAGMA table_info(receipts)")}


def test_mark_downloaded_only_from_received(conn):
    a = add(conn, 1)
    storage.mark_downloaded(conn, a, "/x.jpg", "abc")
    assert storage.get(conn, a)["status"] == "downloaded"


def test_connect_creates_the_database_folder(tmp_path):
    c = storage.connect(str(tmp_path / "a" / "b" / "t.db"))
    assert c.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0
