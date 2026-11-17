from pathlib import Path

import pytest

from bot.config import load

ENV = {"BOT_TOKEN": "t", "ALLOWED_CHAT_IDS": "-100, -200", "ALLOWED_USER_IDS": "1,2"}


def test_defaults_and_ids():
    c = load(ENV)
    assert c.allowed_chats == {-100, -200} and c.allowed_users == {1, 2}
    assert c.recogniser == "glm"
    assert (c.eod_time.hour, c.eod_time.minute) == (22, 0)
    assert str(c.eod_time.tzinfo) == "Asia/Manila"


def test_missing_token_fails_fast():
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        load({})


def test_bad_recogniser():
    with pytest.raises(RuntimeError, match="RECOGNISER"):
        load({**ENV, "RECOGNISER": "gpt"})


def test_allow_rules():
    c = load(ENV)
    assert c.is_allowed(-100, 1)
    assert not c.is_allowed(-999, 1)      # group not allowed
    assert not c.is_allowed(-100, 3)      # submitter not allowed
    assert not c.is_allowed(-100, None)
    assert c.is_allowed_group(-200) and not c.is_allowed_group(5)


def test_default_paths_are_absolute_and_expand_from_relative():
    c = load({"BOT_TOKEN": "t"})
    assert c.storage_dir.is_absolute() and c.storage_dir.name == "images"
    assert Path(c.db_path).is_absolute() and Path(c.db_path).name == "transacocr.db"
