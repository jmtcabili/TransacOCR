from decimal import Decimal

from bot.domain import Parsed
from bot.pipeline import Outcome
from bot.replies import render

TODAY = "2026-05-20"


def outcome(kind, reasons=(), **p):
    base = dict(provider="GCash", transaction_type="send money", amount=Decimal("300"), fee=Decimal("0"),
                total=Decimal("300"), printed_date="2026-05-20", printed_time="19:44", reference_number="8041012628744",
                sender_name="Juan D.", recipient_name="JO••••A C.", recipient_account="****6567")
    return Outcome(kind, 1, -1, 5, parsed=Parsed(**{**base, **p}), reasons=list(reasons))


def test_clean():
    assert render(outcome("clean"), TODAY) == (
        "✅ GCash · send money\n"
        "Amount: 300.00 (fee 0.00, total 300.00)\n"
        "Date: 2026-05-20 19:44\n"
        "Ref: 8041012628744\n"
        "From: Juan D. → To: JO••••A C. ****6567")


def test_needs_review_shows_dashes_and_reasons():
    text = render(outcome("needs_review", ["missing_amount", "missing_reference"], amount=None, fee=None, total=None,
                          reference_number=None, sender_name=None), TODAY)
    assert text.splitlines()[0] == "⚠️ GCash · send money"
    assert "Amount: —" in text and "Ref: —" in text and "From: — →" in text
    assert text.splitlines()[-1] == "Needs review: amount not read, reference number not read"


def test_duplicate():
    assert render(outcome("duplicate"), TODAY) == "♻️ Already recorded: GCash ref 8041012628744 (2026-05-20)."


def test_ocr_error():
    assert render(Outcome("ocr_error", 1, -1, 5, reasons=["ocr_error"]), TODAY) == "⚠️ Couldn't read this, saved for review."


def test_late_date_warning_only_when_date_is_not_today():
    assert "not in today's report" not in render(outcome("clean"), TODAY)
    assert render(outcome("clean"), "2026-05-21").splitlines()[-1] == "🗓 Dated 2026-05-20, not in today's report."


def test_unknown_provider_and_thousands():
    text = render(outcome("clean", provider="other", transaction_type=None, amount=Decimal("12345.5")), TODAY)
    assert text.startswith("✅ Other provider\nAmount: 12,345.50")
