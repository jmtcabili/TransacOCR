from decimal import Decimal

import pytest

from bot.domain import Parsed, dedupe_key, needs_review


def good(**kw):
    base = dict(provider="GCash", amount=Decimal("300"), printed_date="2026-05-20",
                reference_number="8041012628744")
    return Parsed(**{**base, **kw})


def test_clean_receipt_has_no_reasons():
    assert needs_review(good()) == []


@pytest.mark.parametrize("change,reason", [
    ({"amount": None}, "missing_amount"),
    ({"printed_date": None}, "missing_date"),
    ({"reference_number": None}, "missing_reference"),
    ({"reference_number": ""}, "missing_reference"),
    ({"txn_status": "pending"}, "not_successful"),
    ({"currency": "USD"}, "non_php"),
])
def test_each_rule(change, reason):
    assert needs_review(good(**change)) == [reason]


def test_unknown_provider_alone_is_not_needs_review():
    assert needs_review(good(provider="other")) == []


def test_multiple_reasons():
    assert needs_review(good(amount=None, txn_status="failed")) == ["missing_amount", "not_successful"]


def test_dedupe_key():
    assert dedupe_key(-100, good()) == (-100, "GCash", "8041012628744", "2026-05-20")


@pytest.mark.parametrize("change", [{"reference_number": None}, {"printed_date": None}])
def test_dedupe_key_none_when_unidentifiable(change):
    assert dedupe_key(-100, good(**change)) is None


def test_dedupe_key_differs_per_chat_and_date():
    assert dedupe_key(1, good()) != dedupe_key(2, good())
    assert dedupe_key(1, good()) != dedupe_key(1, good(printed_date="2026-05-21"))
