import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot import storage
from bot.config import load
from bot.handlers import ACK, GREETING, Handlers
from bot.images import extract_image


def cfg(tmp_path):
    return load({"BOT_TOKEN": "t", "ALLOWED_CHAT_IDS": "-100", "ALLOWED_USER_IDS": "1",
                 "STORAGE_DIR": str(tmp_path / "img"), "DB_PATH": str(tmp_path / "t.db")})


class FakeMsg:
    def __init__(self, photo=True):
        self.message_id = 5
        self.replies = []
        self._d = {"photo": [{"file_id": "f1", "file_unique_id": "u1", "width": 10, "height": 10},
                             {"file_id": "f2", "file_unique_id": "u2", "width": 99, "height": 99}]} if photo else {"text": "hi"}

    def to_dict(self):
        return self._d

    async def reply_text(self, text):
        self.replies.append(text)


class FakeFile:
    async def download_to_drive(self, path):
        Path(path).write_bytes(b"jpegbytes")


class FakeBot:
    async def get_file(self, file_id):
        return FakeFile()


def update(msg, chat_id=-100, user_id=1, update_id=1):
    return SimpleNamespace(update_id=update_id, effective_message=msg, effective_chat=SimpleNamespace(id=chat_id),
                           effective_user=SimpleNamespace(id=user_id, full_name="Jo"))


CTX = SimpleNamespace(bot=FakeBot())


def run(coro):
    return asyncio.run(coro)


def test_extract_image_photo_picks_largest_and_document_needs_image_mime():
    assert extract_image(FakeMsg().to_dict())["file_id"] == "f2"
    assert extract_image({"document": {"file_id": "d", "file_unique_id": "du", "mime_type": "application/pdf"}}) is None
    d = extract_image({"document": {"file_id": "d", "file_unique_id": "du", "mime_type": "image/png", "file_name": "a.png"}})
    assert d["source"] == "document"


def test_allowed_photo_is_acked_stored_and_processed(tmp_path):
    c, seen = cfg(tmp_path), []
    msg = FakeMsg()
    run(Handlers(c, seen.append).on_image(update(msg), CTX))
    assert msg.replies == [ACK]
    conn = storage.connect(c.db_path)
    row = conn.execute("SELECT * FROM receipts").fetchone()
    assert row["status"] == "downloaded" and Path(row["stored_path"]).read_bytes() == b"jpegbytes"
    assert Path(row["stored_path"]).parent.parent == c.storage_dir
    assert seen == [row["id"]]


@pytest.mark.parametrize("chat_id,user_id", [(-999, 1), (-100, 2)])
def test_not_allowed_gets_no_reply_and_no_row(tmp_path, chat_id, user_id):
    c = cfg(tmp_path)
    msg = FakeMsg()
    run(Handlers(c).on_image(update(msg, chat_id, user_id), CTX))
    assert msg.replies == []
    assert storage.connect(c.db_path).execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


def test_redelivered_update_does_nothing_twice(tmp_path):
    c, seen = cfg(tmp_path), []
    h = Handlers(c, seen.append)
    for _ in range(2):
        msg = FakeMsg()
        run(h.on_image(update(msg, update_id=7), CTX))
    assert len(seen) == 1 and msg.replies == []


def test_non_image_message_is_ignored(tmp_path):
    msg = FakeMsg(photo=False)
    run(Handlers(cfg(tmp_path)).on_image(update(msg), CTX))
    assert msg.replies == []


def test_start_only_in_allowed_group(tmp_path):
    h = Handlers(cfg(tmp_path))
    ok, no = FakeMsg(), FakeMsg()
    run(h.start(update(ok), CTX))
    run(h.start(update(no, chat_id=-999), CTX))
    assert ok.replies == [GREETING] and no.replies == []


def test_download_failure_leaves_receipt_received(tmp_path):
    c, seen = cfg(tmp_path), []

    class Boom:
        async def get_file(self, _):
            raise RuntimeError("net")

    run(Handlers(c, seen.append).on_image(update(FakeMsg()), SimpleNamespace(bot=Boom())))
    row = storage.connect(c.db_path).execute("SELECT status FROM receipts").fetchone()
    assert row["status"] == "received" and seen == []


def test_download_retries_on_timeout_then_succeeds(tmp_path, monkeypatch):
    from telegram.error import TimedOut
    monkeypatch.setattr("bot.handlers.RETRY_DELAY", 0)
    c, seen = cfg(tmp_path), []

    class Flaky:
        calls = 0

        async def get_file(self, _):
            Flaky.calls += 1
            if Flaky.calls < 3:
                raise TimedOut("Timed out")
            return FakeFile()

    run(Handlers(c, seen.append).on_image(update(FakeMsg()), SimpleNamespace(bot=Flaky())))
    row = storage.connect(c.db_path).execute("SELECT status FROM receipts").fetchone()
    assert Flaky.calls == 3 and row["status"] == "downloaded" and len(seen) == 1


def test_download_gives_up_after_three_timeouts(tmp_path, monkeypatch):
    from telegram.error import TimedOut
    monkeypatch.setattr("bot.handlers.RETRY_DELAY", 0)
    c, seen = cfg(tmp_path), []

    class Dead:
        calls = 0

        async def get_file(self, _):
            Dead.calls += 1
            raise TimedOut("Timed out")

    run(Handlers(c, seen.append).on_image(update(FakeMsg()), SimpleNamespace(bot=Dead())))
    row = storage.connect(c.db_path).execute("SELECT status FROM receipts").fetchone()
    assert Dead.calls == 3 and row["status"] == "received" and seen == []
