"""End-to-end `parse()` on rows that mirror real receipts per Provider (trimmed from images/train)."""
from decimal import Decimal

from ocr.parse import parse


def check(p, **expected):
    got = {k: getattr(p, k) for k in expected}
    assert got == expected


def test_gcash(items):
    p = parse(items("JO……A C.", "+63 9.……6567", "Sent via GCash", "Amount 300.00",
                    "Total Amount Sent P300.00", "Ref No. 8041 012 May 20, 2026 7:44", "628744 PM"))
    check(p, provider="GCash", amount=Decimal("300.00"), total=Decimal("300.00"), reference_number="8041012628744",
          printed_date="2026-05-20", printed_time="19:44", txn_status="successful")


def test_gcash_reference_and_date_on_one_row(items):
    p = parse(items("Sent via GCash", "Amount 600.00", "Ref No. 9041 620 530721 Jun 07, 2026 5:36 PM"))
    check(p, reference_number="9041620530721", printed_date="2026-06-07", printed_time="17:36")


def test_maribank(items):
    p = parse(items("Transfer Result", "Transfer Successful!", "PHP 1,000.00", "From LORNA P.", "MariBank:19005486340",
                    "To Jo****a C.", "G-Xchange/ GCash", "Transfer Amount PHP 1,000.00", "Transfer Fee FREE",
                    "Total Amount PHP 1,000.00", "Reference Number 520454", "Transaction Date & Time 27 Sep 2026, 12:43"))
    check(p, provider="MariBank", amount=Decimal("1000.00"), fee=Decimal("0.00"), total=Decimal("1000.00"),
          reference_number="520454", printed_date="2026-09-27", printed_time="12:43")


def test_gotyme_fixes_the_letter_o_read_as_zero(items):
    p = parse(items("To JO****A C*", "From JAMES P***** G*****", "GoTyme Bank", "Amount P300.00", "Fee P0.00",
                    "Total P300.00", "Reference No. IT0260719040833002", "Date 19 Jul 2026 at 12:08 PM"))
    check(p, provider="GoTyme", reference_number="ITO260719040833002", amount=Decimal("300.00"),
          printed_date="2026-07-19", printed_time="12:08")


def test_bpi_reference_ignores_glued_page_noise(items):
    p = parse(items("Transfer successful!", "Tuesday, Sep 08 2026; 03:18:20 PM (GMT +8)", "Confirmation No. 1625115642064",
                    "Transaction Ref. No. 794304 14", "Sent via BPI", "Transfer to", "GCash/G-Xchange",
                    "Transfer amount", "PHP 300.00", "Fee", "PHP 0.00"))
    check(p, provider="BPI", reference_number="794304", amount=Decimal("300.00"), fee=Decimal("0.00"),
          printed_date="2026-09-08", printed_time="15:18")


def test_bdo(items):
    p = parse(items("Sent!", "PHP300.00", "Service Fee PHP 10.00", "Total PHP 310.00", "Send instaPay Money via",
                    "To JO****A C....BCWU", "Created on", "Apr 26, 2026 06:46 PM", "Reference no.", "BN-20260426-31189233",
                    "Invoice no.", "571928"))
    check(p, provider="BDO", amount=Decimal("300.00"), fee=Decimal("10.00"), total=Decimal("310.00"),
          reference_number="BN20260426-31189233".replace("-", ""), printed_date="2026-04-26", printed_time="18:46")


def test_maya(items):
    p = parse(items("Sent money via", "- P300.00 instaPay", "May 10, 2026, 08:09 PM", "Account type G-Xchange Inc. /", "GCash",
                    "Transfer Fee P15.00", "Reference ID 8814 81EE 5425"))
    check(p, provider="Maya", fee=Decimal("15.00"), reference_number="881481EE5425", printed_date="2026-05-10",
          printed_time="20:09")


def test_other_provider_is_parsed_generically_and_not_flagged(items):
    from bot.domain import needs_review
    p = parse(items("InstaPay transfer", "Transaction Date & Time: 16 Sep 2026 (06:34PM)", "Amount", "PHP 300.00",
                    "Name/Pangalan", "JO****A C.", "DWQM4TK3JDNWDBCWU at GCASH", "Reference Number 613043372"))
    check(p, provider="other", amount=Decimal("300.00"), printed_date="2026-09-16", reference_number="613043372")
    assert needs_review(p) == []


def test_pending_status_is_detected(items):
    p = parse(items("Processing", "Pending", "- P310.00", "Transaction fee P10.00"))
    assert p.txn_status == "pending"


def test_bdo_reference_survives_glued_text(items):
    p = parse(items("Sent!", "PHP300.00", "Created on", "Apr 26, 2026 06:46 PM", "Reference no. BN-20260426-31189233 ALWAYS FASTE"))
    assert p.reference_number == "BN2026042631189233"


def test_maribank_reference_is_six_digits(items):
    p = parse(items("Transfer Result", "MariBank:123", "Reference Number 083659 ALLOWED OUT"))
    assert p.reference_number == "083659"


def test_maya_bare_processing_is_pending_but_mariBank_processing_time_is_not(items):
    assert parse(items("Bank transfer to", "- P310.00", "Processing")).txn_status == "pending"
    assert parse(items("Transfer Result", "Processing Time Realtime")).txn_status == "successful"
