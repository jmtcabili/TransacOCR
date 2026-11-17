"""Provider detection: the app/bank that issued the Receipt (the Sender's side).

1. A "Sent via"/"From" anchor naming a Provider.
2. The only Provider named in the text. GCash is never taken from a bare mention: the Recipient's wallet
   is GCash ("G-Xchange Inc. / GCash", "To ... GCASH"), so it counts only via "Sent via" or its signatures.
3. Layout signatures for providers that don't print their own name.
4. Otherwise `other`.
"""
import re

from bot.domain import OTHER

PROVIDER_RX = {name: re.compile(p, re.I) for name, p in {
    "GCash": r"g[\s-]?cash", "Maya": r"\bmaya\b|paymaya", "BDO": r"\bbdo\b|banco de oro",
    "BPI": r"\bbpi\b|bank of the philippine islands", "MariBank": r"mari[\s-]?bank",
    "GoTyme": r"go[\s-]?tyme", "Wise": r"\bwise\b"}.items()}
SENDER_ANCHOR = re.compile(r"^\s*(sent\s*(money\s*)?via|from)\b", re.I)

SIGNATURES = [   # (provider, pattern on the whole text), most specific first
    ("MariBank", re.compile(r"transfer result|transfer method|realtime", re.I)),
    ("BDO", re.compile(r"invoice no|created on", re.I)),
    ("Maya", re.compile(r"reference id|sent money via|bank transfer to|source my wallet|\bgateway\b", re.I)),
    ("GCash", re.compile(r"express send|\bref no\b|transfer from [\d*]+ to", re.I)),
]


def providers_in(text: str) -> list[str]:
    return [n for n, rx in PROVIDER_RX.items() if rx.search(text)]


def detect_provider(items: list[dict], window: int = 4) -> str:
    texts = [i["text"] for i in items]
    for idx, t in enumerate(texts):
        if SENDER_ANCHOR.search(t):
            via = bool(re.search(r"\bsent\s*via\b", t, re.I))   # GCash counts only right after "Sent via"
            for k, u in enumerate(texts[idx: idx + 1 + window]):
                if (found := [p for p in providers_in(u) if p != "GCash" or (via and k <= 1)]):
                    return found[0]
    mentioned = {p for t in texts for p in providers_in(t)} - {"GCash"}
    if len(mentioned) == 1:
        return mentioned.pop()
    if not mentioned:
        whole = "\n".join(texts)
        for name, rx in SIGNATURES:
            if rx.search(whole):
                return name
    return OTHER
