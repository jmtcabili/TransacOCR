"""BDO: references look like BN-20260723-19728424, and neighbouring rows' text can be glued on."""
import re

from bot.domain import Parsed

BN_REF = re.compile(r"\bBN\s*-?\s*(\d{8})\s*-?\s*(\d{8})\b", re.I)


def parse(items: list[dict], p: Parsed) -> None:
    for it in items:
        if (m := BN_REF.search(it["text"])):
            p.reference_number = f"BN{m.group(1)}{m.group(2)}"
            return
