import aiosqlite
import asyncio

DB_PATH = "linkedin_bot.db"

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    linkedin_url TEXT UNIQUE NOT NULL,
    name TEXT,
    headline TEXT,
    company TEXT,
    location TEXT,
    profile_image TEXT,
    email TEXT,
    source TEXT DEFAULT 'search',  -- search, apollo
    status TEXT DEFAULT 'pending',  -- pending, requested, connected, messaged, ignored
    connection_requested_at TEXT,
    connected_at TEXT,
    message_sent_at TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER REFERENCES leads(id),
    body TEXT NOT NULL,
    sent_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT,
    detail TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

async def get_db():
    return await aiosqlite.connect(DB_PATH)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in CREATE_TABLES.strip().split(";"):
            s = stmt.strip()
            if s:
                await db.execute(s)

        # Migrate existing DBs created before the email/source columns existed.
        # SQLite has no "ADD COLUMN IF NOT EXISTS", so check pragma first.
        async with db.execute("PRAGMA table_info(leads)") as cur:
            existing_cols = {row[1] async for row in cur}
        if "email" not in existing_cols:
            await db.execute("ALTER TABLE leads ADD COLUMN email TEXT")
        if "source" not in existing_cols:
            await db.execute("ALTER TABLE leads ADD COLUMN source TEXT DEFAULT 'search'")

        # Default settings
        defaults = {
            "daily_connection_limit": "15",
            "min_delay_seconds": "30",
            "max_delay_seconds": "90",
            "business_hours_start": "9",
            "business_hours_end": "18",
            "connection_message": "",
            "follow_up_message": "Hi {name}, thanks for connecting! {custom}",
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v)
            )
        await db.commit()
