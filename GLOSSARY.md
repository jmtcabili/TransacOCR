# TransacOCR

Reads e-wallet and bank transfer screenshots that people post to a Telegram group, extracts the transaction details, and reports daily totals back to that group.

## Language

**Submitter**:
The Telegram user who posts a receipt image to the bot. Only allowlisted Submitters are served.
_Avoid_: Sender (reserved for the transaction), user, uploader

**Allowed group**:
A Telegram group chat listed in configuration. The bot serves, and sends End-of-day reports to, Allowed groups only, and stays silent everywhere else.
_Avoid_: Whitelisted chat, registered group

**Receipt**:
The screenshot image of a transfer, as submitted, together with what was read from it.
_Avoid_: Screenshot, photo, image (when meaning the record)

**Transaction**:
The money transfer a Receipt shows, with a Sender, a Recipient, an amount, a date and a reference number.
_Avoid_: Payment, transfer (as a noun for the record)

**Sender**:
The party on the Receipt who sent the money.
_Avoid_: Submitter, payer

**Recipient**:
The party on the Receipt who received the money.
_Avoid_: Payee, receiver

**Provider**:
The e-wallet or bank that issued the Receipt (GCash, Maya, BDO, BPI, MariBank, GoTyme, Wise). `other` when none is recognised.
_Avoid_: Bank, app, wallet

**Reference number**:
The Provider's identifier for a Transaction. Together with the Provider it identifies the Transaction uniquely.
_Avoid_: Ref no, transaction ID

**Needs review**:
The state of a Receipt whose amount, date or reference number could not be read, or whose Transaction is not successful. An unrecognised Provider alone does not put a Receipt here. Such a Receipt is listed in the end-of-day report but not counted in its totals.
_Avoid_: Failed, error, unsure

**End-of-day report**:
The daily message to the group covering Transactions whose printed date is that day: the total amount, the Transaction count per Provider, the Needs-review items, and a CSV of the records.
_Avoid_: EOD summary, daily digest
