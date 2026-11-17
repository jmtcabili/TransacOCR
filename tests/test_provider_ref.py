import pytest

from ocr.provider import detect_provider
from ocr.reference import detect_reference


def items(*texts):
    return [{"text": t, "box": [0, i * 30, 500, i * 30 + 20]} for i, t in enumerate(texts)]


@pytest.mark.parametrize("texts,expected", [
    (["Sent via GCash", "Amount 300.00"], "GCash"),
    (["From", "Maya", "BDO savings"], "Maya"),               # the anchor wins over other mentions
    (["Transfer successful", "BPI"], "BPI"),                 # only one mentioned
    (["BPI", "GCash"], "BPI"),                               # GCash is the Recipient's wallet, not the Provider
    (["BPI", "Maya"], "other"),                              # two senders named, no anchor
    (["To JO****A C.", "G-Xchange Inc. / GCash"], "other"),  # GCash only as the destination
    (["Express Send", "Ref No. 1234 567 890123"], "GCash"),  # signature, no name printed
    (["Transfer Result", "Transfer Method instaPay"], "MariBank"),
    (["Sent money via", "InstaPay"], "Maya"),
    (["From", "Janel", "TO joanne", "GCASH"], "other"),
    (["nothing here"], "other"),
    (["go tyme", "Reference No."], "GoTyme"),
    (["Mari Bank"], "MariBank"),
])
def test_detect_provider(texts, expected):
    assert detect_provider(items(*texts)) == expected


@pytest.mark.parametrize("texts,expected", [
    (["Ref No. 8041 012 628744"], "8041012628744"),
    (["Reference No. ITO260831040302011"], "ITO260831040302011"),
    (["Reference Number", "464438"], "464438"),
    (["Ref No.", "Date", "20260101"], None),                 # stops at the next label
    (["Ref No."], None),
    (["no reference here"], None),
])
def test_detect_reference(texts, expected):
    assert detect_reference(items(*texts)) == expected
