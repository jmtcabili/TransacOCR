"""Settings from the environment, plus the allow rules."""
import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo


def _ids(raw: str | None) -> frozenset[int]:
    return frozenset(int(x) for x in (raw or "").replace(" ", "").split(",") if x)


@dataclass(frozen=True)
class Config:
    token: str
    allowed_chats: frozenset[int]      # Allowed groups
    allowed_users: frozenset[int]      # allowlisted Submitters
    storage_dir: Path
    db_path: str
    recogniser: str                    # "glm" | "rapid"
    eod_time: time
    tz: ZoneInfo

    def is_allowed(self, chat_id: int, user_id: int | None) -> bool:
        return chat_id in self.allowed_chats and user_id in self.allowed_users

    def is_allowed_group(self, chat_id: int) -> bool:
        return chat_id in self.allowed_chats


def load(env=None) -> Config:
    env = os.environ if env is None else env
    token = env.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    recogniser = env.get("RECOGNISER", "glm")
    if recogniser not in ("glm", "rapid"):
        raise RuntimeError(f"RECOGNISER must be 'glm' or 'rapid', got {recogniser!r}")
    tz = ZoneInfo(env.get("TZ_NAME", "Asia/Manila"))
    hh, mm = (env.get("EOD_TIME", "22:00")).split(":")
    return Config(
        token=token,
        allowed_chats=_ids(env.get("ALLOWED_CHAT_IDS")),
        allowed_users=_ids(env.get("ALLOWED_USER_IDS")),
        storage_dir=Path(env.get("STORAGE_DIR", "./images")).expanduser().resolve(),
        db_path=str(Path(env.get("DB_PATH", "./transacocr.db")).expanduser().resolve()),
        recogniser=recogniser,
        eod_time=time(int(hh), int(mm), tzinfo=tz),
        tz=tz,
    )
