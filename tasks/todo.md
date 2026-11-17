# Task List: TransacOCR MVP

See `tasks/plan.md` for decisions and risks. Tests run with `pytest tests/<file> -q` (add `pytest` to `bot/requirements.txt` in Task 1).

## Phase 1: Foundation

## Task 1: Domain rules (status, Needs review, dedupe key)

**Description:** Pure functions and types for a parsed Receipt: the fields, the Needs-review rule with its reasons, and the dedupe key.

**Acceptance criteria:**
- [x] `needs_review(parsed)` returns the reasons: missing amount, date or reference number; status not `successful`; currency not PHP.
- [x] `provider = other` alone gives no reasons.
- [x] `dedupe_key()` is `(chat_id, provider, reference_number, printed_date)` and is `None` when the reference number or date is missing.

**Verification:**
- [x] Tests pass: `pytest tests/test_domain.py -q`
- [x] Table-driven cases cover each rule and the `None` key.

**Dependencies:** None

**Files likely touched:**
- `bot/domain.py`
- `tests/test_domain.py`
- `bot/requirements.txt`

**Estimated scope:** Small

## Task 2: Storage layer

**Description:** Extend the SQLite schema from `bot/app.py` with parsed fields (provider, amount, fee, total, currency, printed date and time, reference number, Sender and Recipient names, status, review reasons) and a unique index for the dedupe key. Add functions to insert a Receipt, record a parse result, find a duplicate, and fetch by chat and printed date.

**Acceptance criteria:**
- [x] `update_id` uniqueness is kept for redelivery.
- [x] Inserting a second row with the same non-null dedupe key is reported as a duplicate, not raised.
- [x] Rows with a null key never collide.
- [x] Queries are always scoped by `chat_id`.

**Verification:**
- [x] Tests pass: `pytest tests/test_storage.py -q` (temp-file SQLite)
- [x] Opening an existing `transacocr.db` does not lose rows.

**Dependencies:** Task 1

**Files likely touched:**
- `bot/storage.py`
- `tests/test_storage.py`

**Estimated scope:** Medium

## Task 3: Configuration and allow rules

**Description:** Load config from env: bot token, Allowed group chat IDs, allowlisted Submitter user IDs, `STORAGE_DIR`, `DB_PATH`, `RECOGNISER`, EOD time and zone. Provide `is_allowed(chat_id, user_id)`.

**Acceptance criteria:**
- [x] Missing token fails fast with a clear message.
- [x] A message is served only if the group is an Allowed group and the user is an allowlisted Submitter.
- [x] `RECOGNISER` accepts `glm` or `rapid` only.

**Verification:**
- [x] Tests pass: `pytest tests/test_config.py -q`

**Dependencies:** None

**Files likely touched:**
- `bot/config.py`
- `tests/test_config.py`

**Estimated scope:** Small

### Checkpoint: Foundation
- [ ] All tests pass
- [ ] Review with human before proceeding

## Phase 2: Walking skeleton

## Task 4: Preprocessing

**Description:** EXIF transpose, then resize so the longest side is at most 1600 px. Never mutate the saved original.

**Acceptance criteria:**
- [x] An EXIF-rotated image comes out upright.
- [x] Images smaller than 1600 px are not upscaled.
- [x] The input file on disk is unchanged.

**Verification:**
- [x] Tests pass: `pytest tests/test_preprocess.py -q`

**Dependencies:** None

**Files likely touched:**
- `bot/preprocess.py`
- `tests/test_preprocess.py`

**Estimated scope:** Small

## Task 5: Polling bot: greeting, ack, save image

**Description:** Replace the FastAPI route with a `python-telegram-bot` polling app. `/start` replies with a greeting and usage. A photo or image document from an allowed Submitter in an Allowed group gets an immediate "received" reply, is downloaded, saved to `STORAGE_DIR/<YYYY-MM>/<file_unique_id>.<ext>`, and recorded with status `received`. Everyone else gets no reply. Keep `extract_image()`.

**Acceptance criteria:**
- [x] Photos and image documents are both accepted.
- [x] A non-allowed user or group gets no reply and no row.
- [x] Redelivered updates don't create a second row.
- [x] `/start` works only in an Allowed group.

**Verification:**
- [x] Tests pass: `pytest tests/test_bot_handlers.py -q` (handlers called with fake updates)
- [ ] Manual check: with privacy mode off, a photo in the test group gets "received" and a file appears in `STORAGE_DIR`.

**Dependencies:** Tasks 2, 3

**Files likely touched:**
- `bot/main.py`
- `bot/handlers.py`
- `bot/app.py` (retired)
- `bot/requirements.txt` (`python-telegram-bot[job-queue]`; FastAPI and uvicorn removed)

**Estimated scope:** Medium

### Checkpoint: Skeleton
- [ ] Bot runs by long polling and stores images
- [ ] Review with human before proceeding

## Phase 3: Reading receipts

## Task 6: Hybrid recogniser module

**Description:** Move exp3's `detect`, `merge_rows` and the per-region glm-ocr call into an importable module. Output is the `{text, box 0-1000}` item list. Per-region fallback to RapidOCR text on Ollama error. `RECOGNISER=rapid` skips glm-ocr.

**Acceptance criteria:**
- [x] Same item shape as exp3's `normalize()`.
- [x] An Ollama error on a region falls back to its RapidOCR text and does not abort the image.
- [x] Total failure raises one clear error type for the pipeline to turn into `ocr_error`.
- [x] Models are loaded once, not per image.

**Verification:**
- [x] Tests pass: `pytest tests/test_recogniser.py -q` (glm call stubbed)
- [ ] Manual check: run on 3 images in `images/train` with each `RECOGNISER` value.

**Dependencies:** Task 4

**Files likely touched:**
- `ocr/recognise.py`
- `tests/test_recogniser.py`

**Estimated scope:** Medium

## Task 7: Provider and reference parsing

**Description:** Move exp3's `detect_provider` and `detect_reference` into a module, taking the item list as input.

**Acceptance criteria:**
- [x] Returns `other` when no Provider matches.
- [x] Reference number is cleaned to upper-case alphanumerics.
- [x] On `labels/train.csv` the provider match rate is reported, and the misses are listed in the test output.

**Verification:**
- [x] Tests pass: `pytest tests/test_provider_ref.py -q` (items from a small JSON fixture per Provider)

**Dependencies:** None

**Files likely touched:**
- `ocr/provider.py`
- `ocr/reference.py`
- `tests/test_provider_ref.py`
- `tests/fixtures/`

**Estimated scope:** Medium

## Task 8: Generic amount, date, status, currency parsing

**Description:** Provider-independent parsers for amount (with fee and total), printed date and time, status and currency from the item list. Needs-review checks come from Task 1.

**Acceptance criteria:**
- [x] Handles `₱1,500.00`, `PHP 300.00` and `300.00`.
- [x] Dates in the formats seen in `train.csv` give ISO `YYYY-MM-DD` and 24-hour `HH:MM`.
- [x] `pending` is detected from receipt text.
- [x] Unparseable fields come back as `None`, not an exception.

**Verification:**
- [x] Tests pass: `pytest tests/test_parse_generic.py -q`
- [x] A script prints per-field match rate against `labels/train.csv`.

**Dependencies:** Task 7

**Files likely touched:**
- `ocr/fields.py`
- `tests/test_parse_generic.py`

**Estimated scope:** Medium

## Task 9: Per-provider parsers: GCash

**Description:** GCash is 136 of 316 labelled Receipts. Add layout-specific parsing on top of the generic parser where the generic one misses.

**Acceptance criteria:**
- [x] Amount, date, reference number and Recipient match the labels on at least the agreed threshold (set after Task 8's baseline, proposed 90%).
- [x] Parser is selected by the detected Provider.

**Verification:**
- [x] Tests pass: `pytest tests/test_parse_gcash.py -q`
- [x] Accuracy script prints GCash per-field rates.

**Dependencies:** Task 8

**Files likely touched:**
- `ocr/providers/gcash.py`
- `tests/test_parse_gcash.py`

**Estimated scope:** Medium

## Task 10: Per-provider parsers: MariBank, GoTyme, BPI

**Description:** Same as Task 9 for MariBank (53), GoTyme (47) and BPI (31).

**Acceptance criteria:**
- [x] Each Provider meets the Task 9 threshold on its labelled Receipts.
- [x] BPI's short reference numbers parse intact.

**Verification:**
- [x] Tests pass: `pytest tests/test_parse_maribank.py tests/test_parse_gotyme.py tests/test_parse_bpi.py -q`

**Dependencies:** Task 8

**Files likely touched:**
- `ocr/providers/maribank.py`, `gotyme.py`, `bpi.py`
- `tests/test_parse_*.py`

**Estimated scope:** Medium

## Task 11: Per-provider parsers: BDO, Maya, other

**Description:** BDO (17), Maya (11), and the generic fallback path for `other` (21 labelled).

**Acceptance criteria:**
- [x] BDO and Maya meet the Task 9 threshold, or the gap is recorded in `docs/experiment-log.md` as a known limit.
- [x] `other` uses the generic parser and is not Needs review by Provider alone.

**Verification:**
- [x] Tests pass: `pytest tests/test_parse_bdo.py tests/test_parse_maya.py tests/test_parse_other.py -q`

**Dependencies:** Task 8

**Files likely touched:**
- `ocr/providers/bdo.py`, `maya.py`
- `tests/test_parse_*.py`

**Estimated scope:** Medium

### Checkpoint: Parsing accuracy
- [ ] Per-field, per-Provider accuracy table printed and reviewed
- [ ] Decide whether `RECOGNISER=glm` or `rapid` is the default
- [ ] Review with human before proceeding

## Phase 4: Wire the pipeline

## Task 12: Worker thread and pipeline

**Description:** One worker thread consumes a FIFO queue. For each Receipt: preprocess, recognise, detect Provider, parse, apply Needs-review rules, check for a duplicate, store, then hand the outcome to the reply step. The ack still goes out first (Task 5). OCR failure stores the Receipt as Needs review with reason `ocr_error`.

**Acceptance criteria:**
- [x] Receipts are processed one at a time in arrival order.
- [x] Outcome is one of: clean, needs_review, duplicate, ocr_error.
- [x] A duplicate is not stored as a second Transaction.
- [x] The bot stays responsive (ack and `/start`) while OCR runs.

**Verification:**
- [x] Tests pass: `pytest tests/test_pipeline.py -q` (recogniser stubbed)
- [ ] Manual check: send two photos quickly; both get acks first, results come back in order.

**Dependencies:** Tasks 5, 6, 8, 9, 10, 11

**Files likely touched:**
- `bot/pipeline.py`
- `bot/worker.py`
- `tests/test_pipeline.py`

**Estimated scope:** Medium

## Task 13: Reply formatting

**Description:** Format the result reply for each outcome: clean (✅ layout from the grilling session), Needs review (⚠️, missing fields as `—`), duplicate ("already recorded"), `ocr_error` ("couldn't read this, saved for review"). Add the late-date warning when the printed date isn't today.

**Acceptance criteria:**
- [x] Each outcome has a golden-text test.
- [x] The warning text is "dated YYYY-MM-DD, not in today's report".
- [x] Reference numbers and account digits are shown as stored.

**Verification:**
- [x] Tests pass: `pytest tests/test_replies.py -q`

**Dependencies:** Task 12

**Files likely touched:**
- `bot/replies.py`
- `tests/test_replies.py`

**Estimated scope:** Small

### Checkpoint: End-to-end receipt flow
- [ ] A real receipt in the test group gets ack, then result
- [ ] A resent receipt gets "already recorded"
- [ ] Review with human before proceeding

## Phase 5: End-of-day

## Task 14: Report builder and CSV

**Description:** For a chat and a printed date: PHP total, count per Provider, the Needs-review list, and a CSV with `reference_number, provider, amount, date, time, recipient, status, submitter, received_at`. Message format: `💵 Total: 12,345.50 pesos`, `🧾 Total transactions: 5`, then `- n provider` lines. Zero Transactions gives "No transactions today".

**Acceptance criteria:**
- [x] Only clean Transactions are counted. Needs-review rows are listed only.
- [x] Grouping is by printed date (ADR 0001), not `received_at`.
- [x] Rows from other chats never appear.
- [x] CSV round-trips commas and quotes in names.

**Verification:**
- [x] Tests pass: `pytest tests/test_report.py -q`

**Dependencies:** Task 2

**Files likely touched:**
- `bot/report.py`
- `tests/test_report.py`

**Estimated scope:** Medium

## Task 15: Scheduled EOD and `/report`

**Description:** Schedule a daily PTB JobQueue job at 22:00 Asia/Manila that sends the report and CSV to every Allowed group. Add `/report [YYYY-MM-DD]` for allowlisted Submitters in an Allowed group, defaulting to today.

**Acceptance criteria:**
- [x] The job runs at 22:00 Asia/Manila.
- [x] The CSV is sent as a file attachment, not a link.
- [x] A failure in one group doesn't stop the others.
- [x] A bad date argument gets a usage reply.

**Verification:**
- [x] Tests pass: `pytest tests/test_eod_job.py -q` (job callback called directly)
- [ ] Manual check: `/report` in the test group returns the message and file.

**Dependencies:** Tasks 5, 14

**Files likely touched:**
- `bot/eod.py`
- `bot/main.py`
- `tests/test_eod_job.py`

**Estimated scope:** Medium

### Checkpoint: Complete
- [ ] All tests pass
- [ ] Core flow works end to end, EOD included
- [ ] Review with human before proceeding

## Phase 6: Close out

## Task 16: Evaluation run and docs

**Description:** Run the pipeline over `images/train` against `labels/train.csv` and record per-field accuracy and per-image latency for both `RECOGNISER` values. Update `docs/architecture.md` (long polling, allowlists, JobQueue, cascade still open) and add run instructions.

**Acceptance criteria:**
- [x] A results table is in `docs/experiment-log.md`.
- [x] `docs/architecture.md` open items match what was built.
- [x] README says how to run the bot and set the environment.

**Verification:**
- [ ] Manual check: a fresh checkout follows the README to a running bot.

**Dependencies:** Tasks 12, 15

**Files likely touched:**
- `eval/run_eval.py`
- `docs/experiment-log.md`
- `docs/architecture.md`
- `README.md`

**Estimated scope:** Medium
