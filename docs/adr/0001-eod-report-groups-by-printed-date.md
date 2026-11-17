---
status: accepted
---

# End-of-day report groups Transactions by the date printed on the Receipt

The End-of-day report covers Transactions whose printed date is that day, not those the bot received that day. The report is meant to reflect when money actually moved, and Submitters sometimes post receipts late.

## Considered Options

- **Group by `received_at`** (Manila time): simple, and a late-posted Receipt always lands in the next report. Rejected because it mixes days: a Transaction from the 17th posted on the 18th would be counted as the 18th's money.

## Consequences

- A Receipt posted after its printed day's report has gone out appears in no scheduled report. The bot warns the Submitter in its reply ("dated 2026-11-17, not in today's report"), and `/report [YYYY-MM-DD]` regenerates any day's report on demand.
- A Receipt with no readable date is Needs review and is not counted, since it can't be placed on a day.
- The CSV carries both the printed date and `received_at`.
inclu