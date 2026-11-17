"""GCash: the reference is 13 digits printed "dddd ddd dddddd", often wrapped onto the next row."""
import re

from bot.domain import Parsed
from ocr.reference import REF_LABEL, cut_at_date


def parse(items: list[dict], p: Parsed) -> None:
    for idx, it in enumerate(items):
        m = REF_LABEL.search(it["text"])
        if not m:
            continue
        digits = re.sub(r"\D", "", cut_at_date(it["text"][m.end():]))
        if len(digits) < 13 and idx + 1 < len(items):
            lead = re.match(r"\s*([\d\s]+)", items[idx + 1]["text"])
            if lead:
                digits += re.sub(r"\D", "", lead.group(1))
        if len(digits) >= 13:
            p.reference_number = digits[:13]
        return
