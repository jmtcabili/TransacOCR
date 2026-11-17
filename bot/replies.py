"""Reply text for each outcome."""
from decimal import Decimal

from bot.domain import Parsed
from bot.pipeline import Outcome

DASH = "—"
REASON_TEXT = {
    "missing_amount": "amount not read", "missing_date": "date not read", "missing_reference": "reference number not read",
    "not_successful": "transaction not successful", "non_php": "not in PHP", "ocr_error": "image could not be read",
}


def money(v: Decimal | None) -> str:
    return DASH if v is None else f"{v:,.2f}"


def _lines(p: Parsed) -> list[str]:
    head = p.provider if p.provider != "other" else "Other provider"
    if p.transaction_type:
        head += f" · {p.transaction_type}"
    amount = f"Amount: {money(p.amount)}"
    extras = [f"{k} {money(v)}" for k, v in (("fee", p.fee), ("total", p.total)) if v is not None]
    if extras:
        amount += f" ({', '.join(extras)})"
    when = " ".join(x for x in (p.printed_date, p.printed_time) if x) or DASH
    to = " ".join(x for x in (p.recipient_name, p.recipient_account) if x) or DASH
    return [head, amount, f"Date: {when}", f"Ref: {p.reference_number or DASH}",
            f"From: {p.sender_name or DASH} → To: {to}"]


def render(o: Outcome, today: str) -> str:
    """`today` is the Manila calendar date (YYYY-MM-DD), used for the late-receipt warning."""
    if o.kind == "ocr_error":
        return "⚠️ Couldn't read this, saved for review."
    p = o.parsed
    if o.kind == "duplicate":
        return f"♻️ Already recorded: {p.provider} ref {p.reference_number} ({p.printed_date})."
    lines = _lines(p)
    if o.kind == "clean":
        lines[0] = "✅ " + lines[0]
    else:
        lines[0] = "⚠️ " + lines[0]
        lines.append("Needs review: " + ", ".join(REASON_TEXT.get(r, r) for r in o.reasons))
    if p.printed_date and p.printed_date != today:
        lines.append(f"🗓 Dated {p.printed_date}, not in today's report.")
    return "\n".join(lines)
