"""Items in, Parsed out: Provider, reference, generic fields, then the Provider's own overrides."""
from bot.domain import Parsed
from ocr import fields
from ocr.provider import detect_provider
from ocr.providers import PROVIDER_PARSERS
from ocr.reference import detect_reference


def parse(items: list[dict]) -> Parsed:
    date, time = fields.parse_datetime(items)
    p = Parsed(
        provider=detect_provider(items),
        txn_status=fields.parse_status(items),
        amount=fields.parse_amount(items),
        fee=fields.parse_fee(items),
        total=fields.parse_total(items),
        currency=fields.parse_currency(items),
        printed_date=date,
        printed_time=time,
        reference_number=detect_reference(items),
        sender_name=fields.parse_sender(items),
        recipient_name=fields.parse_recipient(items),
    )
    if (override := PROVIDER_PARSERS.get(p.provider)):
        override(items, p)
    return p
