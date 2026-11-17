"""End-of-day job (daily, JobQueue) and the /report command."""
import logging
from contextlib import closing
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot import storage
from bot.config import Config
from bot.report import build_report, render_csv, render_message

log = logging.getLogger(__name__)
USAGE = "Usage: /report [YYYY-MM-DD] (default: today)"


def today(cfg: Config) -> str:
    return datetime.now(cfg.tz).date().isoformat()


async def send_report(bot, cfg: Config, chat_id: int, day: str) -> None:
    with closing(storage.connect(cfg.db_path)) as conn:
        rep = build_report(conn, chat_id, day, cfg.tz)
    await bot.send_message(chat_id, render_message(rep, is_today=(day == today(cfg))))
    if rep.transactions or rep.review:   # a header-only CSV is noise on a quiet day
        await bot.send_document(chat_id, document=render_csv(rep), filename=f"transactions-{day}.csv")


def eod_job(cfg: Config):
    async def run(context: ContextTypes.DEFAULT_TYPE) -> None:
        day = today(cfg)
        for chat_id in sorted(cfg.allowed_chats):
            try:
                await send_report(context.bot, cfg, chat_id, day)
            except Exception:   # one unreachable group must not stop the others
                log.exception("end-of-day report failed for chat %s", chat_id)
    return run


def report_command(cfg: Config):
    async def run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat, user, msg = update.effective_chat, update.effective_user, update.effective_message
        if not chat or not msg or not cfg.is_allowed(chat.id, user.id if user else None):
            return
        day = today(cfg)
        if context.args:
            try:
                day = datetime.strptime(context.args[0], "%Y-%m-%d").date().isoformat()
            except ValueError:
                await msg.reply_text(USAGE)
                return
        await send_report(context.bot, cfg, chat.id, day)
    return run
