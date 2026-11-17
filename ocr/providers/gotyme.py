"""GoTyme: references are "ITO" + 15 digits; OCR often reads the letter O as a zero."""
import re

from bot.domain import Parsed


def parse(items: list[dict], p: Parsed) -> None:
    ref = p.reference_number
    if ref and (m := re.fullmatch(r"IT[O0](\d{15})", ref)):
        p.reference_number = "ITO" + m.group(1)
