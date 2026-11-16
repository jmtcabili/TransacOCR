import hmac, os, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, status

TOKEN = os.environ["BOT_TOKEN"]
SECRET = os.environ["WEBHOOK_SECRET"]
STORAGE = Path(os.environ.get("STORAGE_DIR", "/srv/transacocr/images"))
DB_PATH = os.environ.get("DB_PATH", "/srv/transacocr/transacocr.db")
API = f"https://api.telegram.org/bot{TOKEN}"
FILE_API = f"https://api.telegram.org/file/bot{TOKEN}"

app = FastAPI()

def db() -> sqlite3.Connection: 
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db() -> None: 
    STORAGE.mkdir(parents=True, exist_ok=True)
    with db() as c: 
        c.execute("""
        CREATE TABLE IF NOT EXISTS receipts(
            id                  INTEGER PRIMARY KEY,
            update_id           INTEGER NOT NULL UNIQUE,  --for idempotency vs retries.
            chat_id             INTEGER NOT NULL, 
            user_id             INTEGER, 
            message_id          INTEGER NOT NULL,
            file_unique_id      TEXT NOT NULL, 
            file_id             TEXT NOT NULL, 
            original_name       TEXT, 
            mime_type           TEXT, 
            file_size           INTEGER, 
            width               INTEGER, 
            height              INTEGER, 
            source              TEXT NOT NULL, 
            stored_path         TEXT, 
            sha256              TEXT, 
            status              TEXT NOT NULL DEFAULT 'received', 
            received_at         TEXT NOT NULL        
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_receipts_status ON receipts(status)")

init_db()

def extract_image(msg: dict) -> dict | None:
    #msg -> msg from telegram

    if msg.get("photo"): 
            p = msg["photo"][-1] #get the photo with the largest size (less compression)
            return dict(source = "photo", 
                        file_id = p["file_id"], 
                        file_unique_id=p["file_unique_id"], 
                        original_name=None, 
                        mime_type="image/jpeg") #tg makes them jpeg

    doc = msg.get("document")
    if doc and (doc.get("mime_type") or "").startswith("image/"): 
         return dict(source="document", 
                     file_id=doc["file_id"], 
                     file_unique_id=doc["file_unique_id"], 
                     file_size=doc.get("file_size"), 
                     width = None, 
                     height = None, 
                     original_name = doc.get("file_name"), 
                     mime_type = doc["mime_type"])
    return None

@app.post("/telegram/webhook")
async def webhook(request: Request, background: BackgroundTasks,
                  x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    # TODO 1: reject bad secret (403). Use hmac.compare_digest against SECRET.

    #check if header is missing or does not match secret token
    if not x_telegram_bot_api_secret_token or not (hmac.compare_digest(x_telegram_bot_api_secret_token.encode(), SECRET.encode())):
         raise HTTPException(
            status_code=403,
            detail="Access forbidden",
        )

    update = await request.json()
    msg = update.get("message")
    img = extract_image(msg) if msg else None
    if not img:
        # TODO 2: non-image message. What do you return so Telegram doesn't retry?
        return {"ok":True}

    try:
        # TODO 3: call insert_receipt(update["update_id"], msg, img)
        insert_receipt(update["update_id"], msg, img)
    except sqlite3.IntegrityError:
        # TODO 4: duplicate -> which status code? Do you start a download?
        #start download only if current update id has no stored_path val 
        background.add_task(recover_stuck)

    except sqlite3.OperationalError:
        # TODO 5: DB unreachable -> which status code? (raise HTTPException)
        raise HTTPException(
            status_code=500,
            detail="DB Unreachable"
        )

    # TODO 6: queue the download with background.add_task(...). What does it receive?
    background.add_task(download_receipt, update["update_id"])
    return {"ok": True}


def insert_receipt(update_id: int, msg: dict, img: dict) -> None:
    """Insert one row per Telegram update.

    Raises sqlite3.IntegrityError on a duplicate update_id (already stored)
    and sqlite3.OperationalError if the DB is unreachable. The caller decides
    the HTTP response for each.
    """
    with db() as c:
        c.execute(
            """INSERT INTO receipts
               (update_id, chat_id, user_id, message_id, file_unique_id, file_id,
                original_name, mime_type, file_size, width, height, source, received_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                update_id,
                msg["chat"]["id"],
                (msg.get("from") or {}).get("id"),
                msg["message_id"],
                img["file_unique_id"],
                img["file_id"],
                img.get("original_name"),
                img.get("mime_type"),
                img.get("file_size"),
                img.get("width"),
                img.get("height"),
                img["source"],
                datetime.now(timezone.utc).isoformat(),
            ),
        )


async def download_receipt(update_id: int) -> None:
    # TODO 8: SELECT the row by update_id to get file_id.
    # TODO 9: getFile -> download -> write file to STORAGE -> UPDATE status/stored_path/sha256.
    # TODO 10: on failure, which status do you set? Should recover_stuck retry it?
    ...


async def recover_stuck() -> None:
    # TODO 11: SELECT rows where status='received' AND stored_path IS NULL.
    # TODO 12: overlapping runs could download the same row twice.
    #          How do you "claim" a row atomically (column or status)?
    # TODO 13: call download_receipt for each; limit how many per run.
    ...
