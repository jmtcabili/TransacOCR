"""MariBank: references are 6 digits; trailing words from the next row can be glued on."""
import re

from bot.domain import Parsed
from ocr.reference import REF_LABEL


def parse(items: list[dict], p: Parsed) -> None:
    for it in items:
        m = REF_LABEL.search(it["text"])
        if m and (d := re.search(r"(?<!\d)\d{6}(?!\d)", it["text"][m.end():])):
            p.reference_number = d.group(0)
            return
