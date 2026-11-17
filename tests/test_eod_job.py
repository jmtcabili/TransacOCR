import asyncio
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from bot import eod, storage
from bot.config import load
from bot.domain import Parsed
from bot.main import build_app
from ocr.recognise import Recogniser


class FakeBot:
    def __init__(self, fail_chat=None):
        self.sent, self.fail_chat = [], fail_chat

    async def send_message(self, chat_id, text):
        if chat_id == self.fail_chat:
            raise RuntimeError("blocked")
        self.sent.append(("msg", chat_id, text))

    async def send_document(self, chat_id, document, filename):
        self.sent.append(("doc", chat_id, filename, document))


@pytest.fixture
def cfg(tmp_path):
    return load({"BOT_TOKEN": "1:a", "ALLOWED_CHAT_IDS": "-1,-2", "ALLOWED_USER_IDS": "1",
                 "STORAGE_DIR": str(tmp_path / "i"), "DB_PATH": str(tmp_path / "t.db")})


def add(cfg, chat, day, n=1):
    conn = storage.connect(cfg.db_path)
    rid = storage.insert_receipt(conn, update_id=n * 10 + abs(chat), chat_id=chat, user_id=1, message_id=1,
                                 img=dict(source="photo", file_id="f", file_unique_id="u"))
    storage.record_result(conn, rid, chat, Parsed(provider="GCash", amount=Decimal("300"), printed_date=day,
                                                  reference_number=f"R{n}{chat}"))


def test_job_is_scheduled_daily_at_22_manila(cfg):
    app = build_app(cfg, recogniser=Recogniser("rapid", engine=object()))
    job = app.job_queue.get_jobs_by_name("end-of-day")[0]
    t = job.trigger
    assert (job.name, str(t.timezone), t.fields[5].expressions[0].first, t.fields[6].expressions[0].first) == \
           ("end-of-day", "Asia/Manila", 22, 0)


def test_job_sends_message_and_csv_to_every_allowed_group(cfg):
    day = eod.today(cfg)
    add(cfg, -1, day); add(cfg, -2, day)
    bot = FakeBot()
    asyncio.run(eod.eod_job(cfg)(SimpleNamespace(bot=bot)))
    kinds = [(k, c) for k, c, *_ in bot.sent]
    assert kinds == [("msg", -2), ("doc", -2), ("msg", -1), ("doc", -1)] or sorted(kinds) == sorted(
        [("msg", -1), ("doc", -1), ("msg", -2), ("doc", -2)])
    doc = next(x for x in bot.sent if x[0] == "doc")
    assert doc[2] == f"transactions-{day}.csv" and isinstance(doc[3], bytes)


def test_one_failing_group_does_not_stop_the_others(cfg):
    add(cfg, -2, eod.today(cfg))
    bot = FakeBot(fail_chat=-1)
    asyncio.run(eod.eod_job(cfg)(SimpleNamespace(bot=bot)))
    assert any(c == -2 for _, c, *_ in bot.sent)


def test_quiet_day_sends_text_only(cfg):
    bot = FakeBot()
    asyncio.run(eod.send_report(bot, cfg, -1, eod.today(cfg)))
    assert [k for k, *_ in bot.sent] == ["msg"] and bot.sent[0][2].endswith("No transactions today.")


def update(chat_id=-1, user_id=1):
    return SimpleNamespace(effective_chat=SimpleNamespace(id=chat_id), effective_user=SimpleNamespace(id=user_id),
                           effective_message=Reply())


class Reply:
    def __init__(self):
        self.replies = []

    async def reply_text(self, t):
        self.replies.append(t)


def test_report_command_regenerates_a_past_day(cfg):
    add(cfg, -1, "2026-05-20")
    bot, u = FakeBot(), update()
    asyncio.run(eod.report_command(cfg)(u, SimpleNamespace(bot=bot, args=["2026-05-20"])))
    assert "2026-05-20" in bot.sent[0][2] and "Total: 300.00 pesos" in bot.sent[0][2] and bot.sent[1][0] == "doc"


def test_report_command_bad_date_gets_usage_and_unauthorised_is_ignored(cfg):
    bot, u = FakeBot(), update()
    asyncio.run(eod.report_command(cfg)(u, SimpleNamespace(bot=bot, args=["20/05/2026"])))
    assert u.effective_message.replies == [eod.USAGE] and bot.sent == []
    u2 = update(user_id=99)
    asyncio.run(eod.report_command(cfg)(u2, SimpleNamespace(bot=bot, args=[])))
    assert u2.effective_message.replies == [] and bot.sent == []
