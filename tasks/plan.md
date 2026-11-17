# Implementation Plan: TransacOCR MVP

Source spec: none. Inputs are the grilling session, `GLOSSARY.md` and `docs/adr/0001-eod-report-groups-by-printed-date.md`. Terms (Submitter, Allowed group, Receipt, Transaction, Needs review, End-of-day report) are used as defined in the glossary.

## Overview

A Telegram bot that long-polls, accepts receipt images from allowlisted Submitters in Allowed groups, replies "received" at once, reads the Receipt with the exp3 hybrid (RapidOCR boxes, glm-ocr per region via Ollama), parses and validates fields per Provider, stores the row and the original image in SQLite and on disk, and replies with the extracted fields. A daily End-of-day report (PHP total, per-Provider counts, Needs-review items, CSV) goes to each Allowed group at 22:00 Asia/Manila.

## Architecture Decisions

- **python-telegram-bot, long polling, JobQueue for EOD.** No public URL needed. The FastAPI webhook in `bot/app.py` is dropped. The SQLite schema and `extract_image()` are kept.
- **One worker thread, FIFO.** The GPU has 4 GB, so receipts are processed one at a time. The ack reply is sent from the event loop before OCR is queued.
- **Hybrid recogniser behind `RECOGNISER=glm|rapid`.** Per-region fallback to RapidOCR text if Ollama errors. exp3 has not been run, so the switch is how we back out.
- **Pure core, thin shell.** Parsing, the Needs-review rule, dedupe key and report building are pure functions with tests. The bot, worker and OCR are thin wrappers around them.
- **Everything scoped by `chat_id`.** Dedupe key is `(chat_id, provider, reference_number, printed_date)`. A Receipt with no reference number or no date can't be deduplicated.
- **Needs review** = missing amount, date or reference number, status other than `successful`, non-PHP currency, or `ocr_error`. `provider = other` alone is not Needs review. Needs-review rows are listed in the report, not counted.
- **EOD by printed date (ADR 0001).** `/report [YYYY-MM-DD]` regenerates any day; a reply warns when the printed date isn't today.
- **Reuse over rewrite.** exp3 notebook code (`detect`, `merge_rows`, `detect_provider`, `detect_reference`) moves into modules. The label set (`labels/train.csv`, 316 rows: GCash 136, MariBank 53, GoTyme 47, BPI 31, other 21, BDO 17, Maya 11) is the test oracle for parsing.
- **Tests:** `pytest`. Tasks below use `pytest tests/<file> -q`.

## Task List

Details for each task (description, acceptance criteria, verification, dependencies, files, scope) are in `tasks/todo.md`.

### Phase 1: Foundation
- [x] Task 1: Domain rules (status, Needs review, dedupe key)
- [x] Task 2: Storage layer
- [x] Task 3: Configuration and allow rules

### Checkpoint: Foundation

### Phase 2: Walking skeleton
- [x] Task 4: Preprocessing
- [x] Task 5: Polling bot: greeting, ack, save image

### Checkpoint: Skeleton

### Phase 3: Reading receipts
- [x] Task 6: Hybrid recogniser module
- [x] Task 7: Provider and reference parsing
- [x] Task 8: Generic amount, date, status, currency parsing
- [x] Task 9: Per-provider parsers: GCash
- [x] Task 10: Per-provider parsers: MariBank, GoTyme, BPI
- [x] Task 11: Per-provider parsers: BDO, Maya, other

### Checkpoint: Parsing accuracy

### Phase 4: Wire the pipeline
- [x] Task 12: Worker thread and pipeline
- [x] Task 13: Reply formatting

### Checkpoint: End-to-end receipt flow

### Phase 5: End-of-day
- [x] Task 14: Report builder and CSV
- [x] Task 15: Scheduled EOD and `/report`

### Checkpoint: Complete

### Phase 6: Close out
- [x] Task 16: Evaluation run and docs

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| glm-ocr is slower or no better than RapidOCR text (exp3 unrun) | High | Run exp3 before Task 6. `RECOGNISER=rapid` is the fallback. Measure latency in Task 16. |
| GTX 1050 Ti (4 GB) can't hold glm-ocr alongside other work | Med | Single worker. Fallback per region. Ollama down is covered by `ocr_error`. |
| Only exp3's provider and reference rules exist. Amount, date, fee, status parsing is new work across 7 Providers | High | Split into Tasks 8–11, test against `train.csv`, highest-volume Provider first. |
| Short reference numbers (BPI 6 digits) collide | Med | Dedupe key includes printed date and chat (Task 1). |
| Privacy mode left on, so the bot never sees group photos | Med | Task 5 manual check. You turn it off in BotFather. |
| PTB JobQueue needs the `job-queue` extra and the process must be up at 22:00 | Low | Add the extra in Task 5. No catch-up in the MVP (decided). |
| Time zone mistakes at the day boundary | Med | Task 14 tests use fixed dates. Printed date has no zone, so no conversion is applied to it. |
| Sender and Submitter confusion in code | Low | Use glossary names for columns and variables. |

## Open Questions

- Should the order of Tasks 9–11 follow label volume (GCash, then MariBank/GoTyme/BPI, then the rest), as drafted?
- Is a day with only Needs-review items still "no transactions today"? I assumed the one-liner plus the Needs-review list.
- What `pytest` and virtualenv layout do you want for `bot/`? There's no test setup in the repo yet.
- exp3 has not been run. Run it before Task 6, or build Task 6 and let Task 16 compare?
