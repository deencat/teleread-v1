import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiosqlite


async def init_db(db_path: str, logger=None) -> aiosqlite.Connection:
    """
    Creates the Phase 1 DB schema (messages_raw).
    Returns an open aiosqlite connection; caller is responsible for `.close()`.
    """

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS messages_raw (
            id                INTEGER  PRIMARY KEY AUTOINCREMENT,
            channel_name      TEXT     NOT NULL,
            message_id        TEXT     NOT NULL,
            sender_name       TEXT,
            message_text      TEXT,
            message_html      TEXT,
            has_media         BOOLEAN  DEFAULT FALSE,
            media_url         TEXT,
            screenshot_path   TEXT,
            timestamp_utc     DATETIME NOT NULL,
            extracted_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            parsed            BOOLEAN  DEFAULT FALSE,
            UNIQUE (channel_name, message_id)
        );
        """
    )
    await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_raw_parsed ON messages_raw(parsed);")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_messages_raw_channel_msg ON messages_raw(channel_name, message_id);")
    await db.commit()

    if logger:
        logger.info("storage.db_initialized", extra={"db_path": db_path})

    return db


async def insert_message_raw(
    db: aiosqlite.Connection,
    *,
    channel_name: str,
    message_id: str,
    sender_name: Optional[str],
    message_text: Optional[str],
    message_html: Optional[str],
    has_media: bool,
    media_url: Optional[str],
    screenshot_path: Optional[str],
    timestamp_utc: dt.datetime,
) -> int:
    """
    Inserts into messages_raw with de-duplication on (channel_name, message_id).
    Returns the number of inserted rows (0 if ignored due to duplication).
    """

    if timestamp_utc.tzinfo is None:
        timestamp_utc = timestamp_utc.replace(tzinfo=dt.timezone.utc)

    # SQLite doesn't have a true boolean type; we store as 0/1.
    has_media_int = 1 if has_media else 0

    cur = await db.execute(
        """
        INSERT OR IGNORE INTO messages_raw (
            channel_name,
            message_id,
            sender_name,
            message_text,
            message_html,
            has_media,
            media_url,
            screenshot_path,
            timestamp_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            channel_name,
            message_id,
            sender_name,
            message_text,
            message_html,
            has_media_int,
            media_url,
            screenshot_path,
            timestamp_utc.isoformat(),
        ),
    )
    await db.commit()

    # aiosqlite's `rowcount` is the rows changed by this statement.
    return int(cur.rowcount or 0)

