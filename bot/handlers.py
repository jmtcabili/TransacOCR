"""Telegram handlers: greeting, instant ack, download and store the original image."""
import asyncio
import hashlib
import logging
from contextlib import closing
from datetime import datetime, timezone
from typing import Callable

from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ContextTypes

from bot import storage
from bot.config import Config
from bot.images import extension, extract_image

log = logging.getLogger(__name__)

GREETING = (
    "👋 TransacOCR\n"
    "Send a receipt screenshot (photo or image file) and I'll read it.\n"
    "/report [YYYY-MM-DD] - the end-of-day report for a day (default: today)"
)
ACK = "📥 Received. Reading it now…"
DOWNLOAD_ATTEMPTS = 3
RETRY_DELAY = 1.0   # seconds, multiplied by the attempt number


class Handlers:
    def __init__(self, cfg: Config, process: Callable[[int], None] | None = None):
        self.cfg = cfg
        self.process = process   # called with the receipt id once the image is stored

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        if chat is None or not self.cfg.is_allowed_group(chat.id):
            return
        await update.effective_message.reply_text(GREETING)

    async def on_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        msg, chat, user = update.effective_message, update.effective_chat, update.effective_user
        if msg is None or chat is None or not self.cfg.is_allowed(chat.id, user.id if user else None):
            return
        img = extract_image(msg.to_dict())
        if img is None:
            return
        with closing(storage.connect(self.cfg.db_path)) as conn:
            receipt_id = storage.insert_receipt(
                conn, update_id=update.update_id, chat_id=chat.id, user_id=user.id, message_id=msg.message_id,
                img=img, submitter_name=user.full_name)
        if receipt_id is None:      # Telegram redelivered this update
            return
        await msg.reply_text(ACK)
        try:
            await self._download(context, receipt_id, img)
        except Exception:
            log.exception("download failed for receipt %s", receipt_id)   # stays 'received' for a later retry
            return
        if self.process:
            self.process(receipt_id)

    async def _download(self, context, receipt_id: int, img: dict) -> None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        folder = self.cfg.storage_dir / month
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{img['file_unique_id']}{extension(img)}"
        for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
            try:
                tg_file = await context.bot.get_file(img["file_id"])
                await tg_file.download_to_drive(path)
                break
            except (TimedOut, NetworkError):
                if attempt == DOWNLOAD_ATTEMPTS:
                    raise
                log.warning("download attempt %s/%s timed out, retrying", attempt, DOWNLOAD_ATTEMPTS)
                await asyncio.sleep(RETRY_DELAY * attempt)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with closing(storage.connect(self.cfg.db_path)) as conn:
            storage.mark_downloaded(conn, receipt_id, str(path), digest)
