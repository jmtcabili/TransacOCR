from decimal import Decimal

import pytest

from ocr import fields


@pytest.mark.parametrize("text,expected", [
    ("₱1,500.00", Decimal("1500.00")), ("PHP 300.00", Decimal("300.00")), ("P300.00", Decimal("300.00")),
    ("PHP300.00", Decimal("300.00")), ("- ₱310.00", Decimal("310.00")), ("no money", None), ("ref 8041012", None),
])
def test_money_in(text, expected):
    got = fields.money_in(text)
    assert (None if got is None else abs(got)) == expected


@pytest.mark.parametrize("texts,expected", [
    (["Amount 300.00", "Total Amount Sent P300.00"], Decimal("300.00")),
    (["Transfer Amount PHP 1,000.00", "Total Amount PHP 1,010.00"], Decimal("1000.00")),
    (["Sent!", "PHP300.00", "Service Fee PHP 10.00", "Total PHP 310.00"], Decimal("300.00")),   # standalone figure
    (["Amount", "Date & Time", "May 10, 2026 2:23 PM -300.00"], Decimal("300.00")),              # signed, no mark
    (["Transfer successful"], None),
])
def test_parse_amount(items, texts, expected):
    assert fields.parse_amount(items(*texts)) == expected


@pytest.mark.parametrize("texts,fee,total", [
    (["Transfer Fee FREE", "Total Amount PHP 300.00"], Decimal("0.00"), Decimal("300.00")),
    (["Fee", "PHP 10.00"], Decimal("10.00"), None),
    (["Service Fee PHP 10.00", "Total PHP 310.00"], Decimal("10.00"), Decimal("310.00")),
    (["Amount 300.00"], None, None),
])
def test_parse_fee_and_total(items, texts, fee, total):
    assert fields.parse_fee(items(*texts)) == fee and fields.parse_total(items(*texts)) == total


@pytest.mark.parametrize("texts,expected", [
    (["May 20, 2026 7:44 PM"], ("2026-05-20", "19:44")),
    (["31 Aug 2026 at 12:03 PM"], ("2026-08-31", "12:03")),
    (["27 Sep 2026, 12:43"], ("2026-09-27", "12:43")),
    (["Saturday, May 23 2026; 03:32:11 PM (GMT +8)"], ("2026-05-23", "15:32")),
    (["Aug 29, 2026 • 12:45 PM (GMT +8)"], ("2026-08-29", "12:45")),
    (["Transaction Date & Time: 16 Sep 2026 (06:34PM)"], ("2026-09-16", "18:34")),
    (["Ref No. 3044758 373519 Sep 06,2026 4:30 PM"], ("2026-09-06", "16:30")),
    (["Ref No. 8041 012 May 20, 2026 7:44", "628744 PM"], ("2026-05-20", "19:44")),   # PM wrapped to the next row
    (["Date 09/11/2026 08:15 AM"], ("2026-11-09", "08:15")),                          # day first
    (["12:00 AM", "Jan 02, 2026 12:00 AM"], ("2026-01-02", "00:00")),
    (["Jan 02, 2026"], ("2026-01-02", None)),
    (["no date"], (None, None)),
    (["Feb 40, 2026 1:00 PM"], (None, None)),                                          # impossible day
])
def test_parse_datetime(items, texts, expected):
    assert fields.parse_datetime(items(*texts)) == expected


@pytest.mark.parametrize("texts,expected", [
    (["Transfer successful!"], "successful"), (["Status: Pending"], "pending"),
    (["Processing Time Realtime"], "successful"), (["Transfer failed"], "failed"),
])
def test_parse_status(items, texts, expected):
    assert fields.parse_status(items(*texts)) == expected


def test_parse_currency(items):
    assert fields.parse_currency(items("You sent", "USD 25.00")) == "USD"
    assert fields.parse_currency(items("PHP 25.00")) == "PHP"


@pytest.mark.parametrize("texts,recipient,sender", [
    (["To JO****A C.", "From LORNA P."], "JO****A C.", "LORNA P."),
    (["JO••••A C.", "Sent via GCash"], "JO••••A C.", None),
    (["Jo****a C.", "G-Xchange / GCash"], "Jo****a C.", None),
    (["From 0949471**** to 0917885****"], None, None),
])
def test_recipient_and_sender(items, texts, recipient, sender):
    assert fields.parse_recipient(items(*texts)) == recipient and fields.parse_sender(items(*texts)) == sender
