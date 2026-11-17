"""Pure domain rules: what a parsed Receipt is, when it Needs review, and its dedupe key."""
from dataclasses import dataclass
from decimal import Decimal

PROVIDERS = ("GCash", "Maya", "BDO", "BPI", "MariBank", "GoTyme", "Wise")
OTHER = "other"


@dataclass
class Parsed:
    provider: str = OTHER
    txn_status: str = "successful"
    transaction_type: str | None = None
    amount: Decimal | None = None
    fee: Decimal | None = None
    total: Decimal | None = None
    currency: str = "PHP"
    printed_date: str | None = None   # ISO YYYY-MM-DD, as printed on the Receipt
    printed_time: str | None = None   # HH:MM, 24-hour
    reference_number: str | None = None
    sender_name: str | None = None
    recipient_name: str | None = None
    recipient_account: str | None = None


def needs_review(p: Parsed) -> list[str]:
    """Reasons a Receipt Needs review. An unrecognised Provider alone is not one."""
    reasons = []
    if p.amount is None:
        reasons.append("missing_amount")
    if not p.printed_date:
        reasons.append("missing_date")
    if not p.reference_number:
        reasons.append("missing_reference")
    if p.txn_status != "successful":
        reasons.append("not_successful")
    if p.currency != "PHP":
        reasons.append("non_php")
    return reasons


def dedupe_key(chat_id: int, p: Parsed) -> tuple | None:
    """Identity of a Transaction within a chat; None when it can't be deduplicated."""
    if not p.reference_number or not p.printed_date:
        return None
    return (chat_id, p.provider, p.reference_number, p.printed_date)
