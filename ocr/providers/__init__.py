"""Per-provider overrides. Each takes (items, parsed) and fixes `parsed` in place where the generic parse misses."""
from typing import Callable

from bot.domain import Parsed
from ocr.providers import bdo, bpi, gcash, gotyme, maribank

PROVIDER_PARSERS: dict[str, Callable[[list[dict], Parsed], None]] = {
    "GCash": gcash.parse,
    "GoTyme": gotyme.parse,
    "BPI": bpi.parse,
    "BDO": bdo.parse,
    "MariBank": maribank.parse,
}
