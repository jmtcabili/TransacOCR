"""Entry point: python -m bot.main"""
import asyncio
import logging
from datetime import datetime

from telegram import ReplyParameters
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot import config
from bot.eod import eod_job, report_command
from bot.handlers import Handlers
from bot.pipeline import process_receipt
from bot.replies import render
from bot.worker import Worker
from ocr.recognise import Recogniser
from dotenv import load_dotenv

load_dotenv()


log = logging.getLogger(__name__)


def build_app(cfg: config.Config, recogniser=None) -> Application:
    recogniser = recogniser or Recogniser(cfg.recogniser)
    # PTB's defaults (5 s connect/read/write, 1 s pool) are too tight for file downloads on a slow link.
    app = (Application.builder().token(cfg.token)
           .connect_timeout(20).read_timeout(30).write_timeout(30).pool_timeout(10)
           .get_updates_connect_timeout(20).get_updates_read_timeout(30)
           .build())
    holder: dict = {}

    def deliver(outcome) -> None:
        """Runs on the worker thread: hand the reply to the bot's event loop."""
        today = datetime.now(cfg.tz).date().isoformat()
        coro = app.bot.send_message(outcome.chat_id, render(outcome, today),
                                    reply_parameters=ReplyParameters(outcome.message_id, allow_sending_without_reply=True))
        fut = asyncio.run_coroutine_threadsafe(coro, holder["loop"])
        fut.add_done_callback(lambda f: f.exception() and log.error("reply failed: %s", f.exception()))

    worker = Worker(lambda rid: process_receipt(cfg, recogniser, rid), deliver)
    h = Handlers(cfg, worker.submit)
    app.add_handler(CommandHandler("start", h.start))
    app.add_handler(CommandHandler("report", report_command(cfg)))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, h.on_image))

    async def post_init(application: Application) -> None:
        holder["loop"] = asyncio.get_running_loop()
        worker.start()

    async def post_shutdown(application: Application) -> None:
        worker.stop()

    app.job_queue.run_daily(eod_job(cfg), time=cfg.eod_time, name="end-of-day")
    app.post_init, app.post_shutdown = post_init, post_shutdown
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    build_app(config.load()).run_polling()


if __name__ == "__main__":
    main()
