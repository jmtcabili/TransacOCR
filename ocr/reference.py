"""Reference number detection (from exp2/exp3)."""
import re

REF_LABEL = re.compile(r"\bref(?:erence)?\.?\s*(?:no\.?|number|id)(?![a-z])", re.I)
OTHER_LABEL = re.compile(r"^\s*(date|amount|fee|total|from|to|sent|transfer|trace|status|time)\b", re.I)
_digits = lambda s: len(re.findall(r"\d", s))
_clean_ref = lambda s: re.sub(r"[^A-Za-z0-9]", "", s).upper()
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# A date printed on the same row as the label ("Ref No. 9041 620 530721 Jun 07, 2026 5:36 PM") is not part of the number.
_DATE_START = re.compile(rf"\b{_MON}\s+\d{{1,2}}\b|\b\d{{1,2}}\s+{_MON}\s+\d{{4}}", re.I)


def cut_at_date(text: str) -> str:
    m = _DATE_START.search(text)
    return text[:m.start()] if m else text


def detect_reference(items: list[dict], window: int = 2) -> str | None:
    for idx, it in enumerate(items):
        m = REF_LABEL.search(it["text"])
        if not m:
            continue
        rest = cut_at_date(it["text"][m.end():]).strip(" :#.-")
        if _digits(rest) >= 4:
            value = rest
            if idx + 1 < len(items):
                nxt = items[idx + 1]
                if re.fullmatch(r"[\d\s-]{4,}", nxt["text"].strip()) and 0 <= nxt["box"][1] - it["box"][3] <= 25:
                    value += nxt["text"]
            return _clean_ref(value)
        for nxt in items[idx + 1: idx + 1 + window]:
            t = nxt["text"].strip()
            if OTHER_LABEL.search(t):
                break
            if _digits(t) >= 4:
                return _clean_ref(t)
    return None
