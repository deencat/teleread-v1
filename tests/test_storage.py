import datetime as dt

import pytest

from src.storage import init_db, insert_message_raw


@pytest.mark.asyncio
async def test_init_db_creates_messages_raw(tmp_path):
    db_path = str(tmp_path / "signals.db")
    db = await init_db(db_path)
    try:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages_raw';"
        )
        row = await cur.fetchone()
        assert row is not None
        assert row[0] == "messages_raw"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_insert_message_raw_deduplicates(tmp_path):
    db_path = str(tmp_path / "signals.db")
    db = await init_db(db_path)
    try:
        ts = dt.datetime.now(dt.timezone.utc)

        inserted_1 = await insert_message_raw(
            db,
            channel_name="test_channel",
            message_id="m1",
            sender_name="alice",
            message_text="hello",
            message_html="<p>hello</p>",
            has_media=False,
            media_url=None,
            screenshot_path=None,
            timestamp_utc=ts,
        )
        inserted_2 = await insert_message_raw(
            db,
            channel_name="test_channel",
            message_id="m1",
            sender_name="alice",
            message_text="hello",
            message_html="<p>hello</p>",
            has_media=False,
            media_url=None,
            screenshot_path=None,
            timestamp_utc=ts,
        )

        assert inserted_1 == 1
        assert inserted_2 == 0

        cur = await db.execute("SELECT COUNT(*) FROM messages_raw;")
        count_row = await cur.fetchone()
        assert count_row[0] == 1
    finally:
        await db.close()

