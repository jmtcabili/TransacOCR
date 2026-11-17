from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from bot import storage
from bot.config import load
from bot.pipeline import process_receipt
from bot.worker import Worker
from ocr.recognise import OcrError
from tests.conftest import make_items

GCASH = make_items("Sent via GCash", "Amount 300.00", "Total Amount Sent P300.00",
                   "Ref No. 8041 012 628744", "May 20, 2026 7:44 PM")


class FakeRecogniser:
    def __init__(self, items=None, error=None):
        self.items, self.error, self.calls = items, error, 0

    def read(self, img):
        self.calls += 1
        if self.error:
            raise self.error
        return self.items


@pytest.fixture
def cfg(tmp_path):
    return load({"BOT_TOKEN": "t", "ALLOWED_CHAT_IDS": "-1", "ALLOWED_USER_IDS": "1",
                 "STORAGE_DIR": str(tmp_path / "img"), "DB_PATH": str(tmp_path / "t.db")})


def add_receipt(cfg, tmp_path, update_id=1, chat_id=-1, valid_image=True):
    path = tmp_path / f"{update_id}.jpg"
    if valid_image:
        Image.new("RGB", (50, 50)).save(path)
    else:
        path.write_bytes(b"not an image")
    conn = storage.connect(cfg.db_path)
    rid = storage.insert_receipt(conn, update_id=update_id, chat_id=chat_id, user_id=1, message_id=update_id,
                                 img=dict(source="photo", file_id="f", file_unique_id=f"u{update_id}"))
    storage.mark_downloaded(conn, rid, str(path), "x")
    return rid


def test_clean_receipt(cfg, tmp_path):
    o = process_receipt(cfg, FakeRecogniser(GCASH), add_receipt(cfg, tmp_path))
    assert o.kind == "clean" and o.parsed.amount == Decimal("300.00") and o.reasons == []
    row = storage.get(storage.connect(cfg.db_path), o.receipt_id)
    assert (row["status"], row["outcome"], row["reference_number"]) == ("done", "clean", "8041012628744")


def test_same_receipt_twice_is_a_duplicate(cfg, tmp_path):
    rec = FakeRecogniser(GCASH)
    first = process_receipt(cfg, rec, add_receipt(cfg, tmp_path, 1))
    second = process_receipt(cfg, rec, add_receipt(cfg, tmp_path, 2))
    assert second.kind == "duplicate" and second.duplicate_of == first.receipt_id


def test_missing_fields_need_review(cfg, tmp_path):
    o = process_receipt(cfg, FakeRecogniser(make_items("Sent via GCash")), add_receipt(cfg, tmp_path))
    assert o.kind == "needs_review"
    assert set(o.reasons) == {"missing_amount", "missing_date", "missing_reference"}


@pytest.mark.parametrize("recogniser,valid", [(FakeRecogniser(error=OcrError("boom")), True),
                                              (FakeRecogniser(GCASH), False)])
def test_unreadable_image_becomes_ocr_error(cfg, tmp_path, recogniser, valid):
    o = process_receipt(cfg, recogniser, add_receipt(cfg, tmp_path, valid_image=valid))
    assert o.kind == "ocr_error"
    row = storage.get(storage.connect(cfg.db_path), o.receipt_id)
    assert (row["outcome"], row["review_reasons"]) == ("needs_review", "ocr_error")


def test_worker_processes_in_arrival_order_one_at_a_time():
    import threading
    seen, active, overlap = [], [0], []

    def process(i):
        active[0] += 1
        overlap.append(active[0] > 1)
        seen.append(i)
        active[0] -= 1
        return i

    delivered = []
    w = Worker(process, delivered.append)
    w.start()
    for i in range(20):
        w.submit(i)
    w.join()
    w.stop()
    assert seen == list(range(20)) == delivered and not any(overlap)


def test_worker_survives_a_failing_receipt():
    delivered = []

    def process(i):
        if i == 1:
            raise RuntimeError("bad")
        return i

    w = Worker(process, delivered.append)
    w.start()
    for i in range(3):
        w.submit(i)
    w.join()
    w.stop()
    assert delivered == [0, 2]
