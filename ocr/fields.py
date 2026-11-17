"""Provider-independent field parsers. Each takes the item list ({text, box}) and returns a value or None."""
import re
from decimal import Decimal

MONEY = re.compile(r"(?<![\d.,])-?\s*(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?!\d)")
CURRENCY_MARK = re.compile(r"₱|PHP|(?<![A-Za-z])P(?=\s?\d)", re.I)
_STOP = re.compile(r"^\s*(amount|total|fee|transfer|service|reference|ref|date|from|to|sent|status|time)\b", re.I)

MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATE_RX = [
    re.compile(rf"{_MON}\s+(\d{{1,2}}),?\s*(\d{{4}})", re.I),             # May 20, 2026 / May 23 2026
    re.compile(rf"(\d{{1,2}})\s+{_MON},?\s+(\d{{4}})", re.I),             # 31 Aug 2026
]
NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)")  # dd/mm/yyyy (Philippine order)
TIME_RX = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?::\d{2})?\s*([apf]\.?m\.?)?", re.I)
CURRENCY_CODE = re.compile(r"\b(USD|EUR|GBP|SGD|AUD|JPY|HKD|CAD)\b")


def money_in(text: str) -> Decimal | None:
    m = MONEY.search(text)
    return Decimal(m.group(1).replace(",", "") + "." + m.group(2)) if m else None


def money_after_label(items, label: re.Pattern, window: int = 2, allow_free: bool = False) -> Decimal | None:
    """The amount printed after `label`, on the same item or on one of the next few."""
    for idx, it in enumerate(items):
        m = label.search(it["text"])
        if not m:
            continue
        rest = it["text"][m.end():]
        if allow_free and re.search(r"\bfree\b", rest, re.I):
            return Decimal("0.00")
        if (v := money_in(rest)) is not None:
            return v
        for nxt in items[idx + 1: idx + 1 + window]:
            if allow_free and re.fullmatch(r"\s*free\s*", nxt["text"], re.I):
                return Decimal("0.00")
            if (v := money_in(nxt["text"])) is not None:
                return v
            if _STOP.search(nxt["text"]):
                break
    return None


AMOUNT_LABELS = [re.compile(p, re.I) for p in (
    r"(?<!total )(?<!total\s\s)\b(?:transfer\s+)?amount\b(?!\s+sent)",
    r"(?<!total )\bamount\s+sent\b",
    r"\btotal\s+amount(?:\s+sent)?\b",
)]
FEE_LABEL = re.compile(r"\b(?:transfer\s+|service\s+)?(?:fee|charge)s?\b", re.I)
TOTAL_LABEL = re.compile(r"\btotal(?:\s+amount)?(?:\s+sent)?\b", re.I)


def parse_amount(items) -> Decimal | None:
    for label in AMOUNT_LABELS:
        if (v := money_after_label(items, label)) is not None:
            return abs(v)
    plain = [it for it in items if not FEE_LABEL.search(it["text"]) and not TOTAL_LABEL.search(it["text"])]
    for it in plain:   # a standalone currency-marked figure, e.g. "PHP 1,000.00" or "P300.00"
        if CURRENCY_MARK.search(it["text"]) and (v := money_in(it["text"])) is not None:
            return abs(v)
    for it in plain:   # a signed figure with no currency mark, e.g. "May 10, 2026 2:23 PM -300.00"
        if (m := re.search(r"-\s*(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2})(?!\d)", it["text"])):
            return Decimal(m.group(1).replace(",", "") + "." + m.group(2))
    return None


def parse_fee(items) -> Decimal | None:
    v = money_after_label(items, FEE_LABEL, allow_free=True)
    return None if v is None else abs(v)


def parse_total(items) -> Decimal | None:
    v = money_after_label(items, TOTAL_LABEL)
    return None if v is None else abs(v)


def _iso(y: int, mo: int, d: int) -> str | None:
    return f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= 2100 else None


def _find_date(text: str):
    """(iso_date, end_index) of the first date in `text`."""
    best = None
    for k, rx in enumerate(DATE_RX):
        m = rx.search(text)
        if not m:
            continue
        mon, day, year = (m.group(1), m.group(2), m.group(3)) if k == 0 else (m.group(2), m.group(1), m.group(3))
        iso = _iso(int(year), MONTHS[mon.lower()[:3]], int(day))
        if iso and (best is None or m.start() < best[2]):
            best = (iso, m.end(), m.start())
    m = NUMERIC_DATE.search(text)
    if m and (iso := _iso(int(m.group(3)), int(m.group(2)), int(m.group(1)))) and (best is None or m.start() < best[2]):
        best = (iso, m.end(), m.start())
    return (best[0], best[1]) if best else None


def _to_24h(h: int, mi: int, ap: str | None) -> str | None:
    if ap:
        pm = ap.lower()[0] in "pf"   # OCR often reads PM as FM
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if pm else 0)
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def parse_datetime(items) -> tuple[str | None, str | None]:
    """(ISO date, HH:MM 24h) from the first item carrying a date; the time may be on the same or next item."""
    for idx, it in enumerate(items):
        found = _find_date(it["text"])
        if not found:
            continue
        iso, end = found
        nxt = items[idx + 1]["text"] if idx + 1 < len(items) else ""
        for same_row, text in ((True, it["text"][end:]), (False, nxt)):
            if (m := TIME_RX.search(text)):
                ap = m.group(3)
                if not ap and same_row:   # "7:44" ends this row, "628744 PM" starts the next
                    if (a := re.match(r"\s*(?:[\d\s-]*\s)?([apf]\.?m\.?)\b", nxt, re.I)):
                        ap = a.group(1)
                return iso, _to_24h(int(m.group(1)), int(m.group(2)), ap)
        return iso, None
    return None, None


def parse_status(items) -> str:
    text = " ".join(i["text"] for i in items)
    if re.search(r"\bpending\b|\bin progress\b", text, re.I) or any(
            re.fullmatch(r"\s*processing\s*", i["text"], re.I) for i in items):   # Maya shows a bare "Processing"
        return "pending"
    if re.search(r"\bfailed\b|\bunsuccessful\b|\bdeclined\b|\brejected\b", text, re.I):
        return "failed"
    return "successful"


def parse_currency(items) -> str:
    m = CURRENCY_CODE.search(" ".join(i["text"] for i in items))
    return m.group(1) if m else "PHP"


# Receipts here go to masked names like "JO****A C." / "JO••••A C." / "Jo****a C.".
MASKED_NAME = re.compile(r"\b[A-Za-z]{2}[*•…·.]{2,}[A-Za-z]\.?(?:\s?[A-Za-z][.*]*)?")
FROM_NAME = re.compile(r"^\s*from\s+([A-Za-z][A-Za-z.'\- ]{2,}?)\s*$", re.I)


def parse_recipient(items) -> str | None:
    for it in items:
        if (m := MASKED_NAME.search(it["text"])):
            return m.group(0).strip()
    return None


def parse_sender(items) -> str | None:
    for it in items:
        if (m := FROM_NAME.match(it["text"])) and not re.search(r"\d", m.group(1)):
            return m.group(1).strip()
    return None
