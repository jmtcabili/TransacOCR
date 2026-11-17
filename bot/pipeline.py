"""One Receipt through preprocess -> recognise -> parse -> Needs-review rules -> dedupe -> store."""
import logging
from contextlib import closing
from dataclasses import dataclass, field

from bot import storage
from bot.config import Config
from bot.domain import Parsed
from bot.preprocess import preprocess
from ocr.parse import parse
from ocr.recognise import OcrError, Recogniser

log = logging.getLogger(__name__)


@dataclass
class Outcome:
    kind: str                       # clean | needs_review | duplicate | ocr_error
    receipt_id: int
    chat_id: int
    message_id: int
    parsed: Parsed | None = None
    reasons: list[str] = field(default_factory=list)
    duplicate_of: int | None = None


def process_receipt(cfg: Config, recogniser: Recogniser, receipt_id: int) -> Outcome:
    with closing(storage.connect(cfg.db_path)) as conn:
        row = storage.get(conn, receipt_id)
        base = dict(receipt_id=receipt_id, chat_id=row["chat_id"], message_id=row["message_id"])
        try:
            items = recogniser.read(preprocess(row["stored_path"]))
        except (OcrError, OSError, ValueError) as e:   # unreadable image or failed detection
            log.warning("receipt %s could not be read: %s", receipt_id, e)
            storage.record_error(conn, receipt_id, "ocr_error")
            return Outcome("ocr_error", reasons=["ocr_error"], **base)
        parsed = parse(items)
        kind, reasons, dup = storage.record_result(conn, receipt_id, row["chat_id"], parsed)
        return Outcome(kind, parsed=parsed, reasons=reasons, duplicate_of=dup, **base)
