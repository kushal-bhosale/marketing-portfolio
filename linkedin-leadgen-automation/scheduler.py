"""
Background scheduler: polls for new connections and sends follow-up messages.
Respects daily limits and business hours.
"""
import asyncio
import logging
from datetime import datetime, date
import aiosqlite
from database import DB_PATH

logger = logging.getLogger(__name__)


async def get_setting(db, key: str, default: str = "") -> str:
    async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
        row = await cur.fetchone()
        return row[0] if row else default


async def log_activity(db, action: str, detail: str):
    await db.execute(
        "INSERT INTO activity_log(action, detail) VALUES (?,?)", (action, detail)
    )
    await db.commit()


async def is_business_hours(db) -> bool:
    start = int(await get_setting(db, "business_hours_start", "9"))
    end = int(await get_setting(db, "business_hours_end", "18"))
    hour = datetime.now().hour
    return start <= hour < end


async def connections_sent_today(db) -> int:
    today = date.today().isoformat()
    async with db.execute(
        "SELECT COUNT(*) FROM leads WHERE status='requested' "
        "AND DATE(connection_requested_at)=?",
        (today,),
    ) as cur:
        row = await cur.fetchone()
        return row[0] if row else 0


async def run_connection_queue():
    """Send queued connection requests respecting limits."""
    from linkedin import get_bot
    import random

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        if not await is_business_hours(db):
            logger.info("Outside business hours, skipping connection queue.")
            return

        limit = int(await get_setting(db, "daily_connection_limit", "15"))
        sent_today = await connections_sent_today(db)
        remaining = limit - sent_today

        if remaining <= 0:
            logger.info(f"Daily limit of {limit} reached.")
            return

        min_delay = float(await get_setting(db, "min_delay_seconds", "30"))
        max_delay = float(await get_setting(db, "max_delay_seconds", "90"))
        note = await get_setting(db, "connection_message", "")

        # Get pending leads queued for connection
        async with db.execute(
            "SELECT * FROM leads WHERE status='queued' LIMIT ?", (remaining,)
        ) as cur:
            leads = await cur.fetchall()

        bot = await get_bot()

        for lead in leads:
            personalized_note = note.replace("{name}", lead["name"].split()[0]) if note else ""
            success = await bot.send_connection_request(lead["linkedin_url"], personalized_note)
            if success:
                await db.execute(
                    "UPDATE leads SET status='requested', connection_requested_at=datetime('now') WHERE id=?",
                    (lead["id"],),
                )
                await log_activity(db, "connection_request", f"Sent to {lead['name']} ({lead['linkedin_url']})")
            else:
                await log_activity(db, "connection_failed", f"Failed for {lead['name']}")
            await db.commit()

            delay = random.uniform(min_delay, max_delay)
            logger.info(f"Waiting {delay:.0f}s before next action...")
            await asyncio.sleep(delay)


async def run_acceptance_check():
    """Check for new connections and send follow-up messages."""
    from linkedin import get_bot
    import random

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        follow_up_template = await get_setting(
            db, "follow_up_message", "Hi {name}, thanks for connecting!"
        )
        min_delay = float(await get_setting(db, "min_delay_seconds", "30"))
        max_delay = float(await get_setting(db, "max_delay_seconds", "90"))

        bot = await get_bot()
        connected_urls = await bot.check_new_connections()

        for url in connected_urls:
            # Check if this is a lead we requested
            async with db.execute(
                "SELECT * FROM leads WHERE linkedin_url=? AND status='requested'", (url,)
            ) as cur:
                lead = await cur.fetchone()

            if lead:
                # Mark as connected
                await db.execute(
                    "UPDATE leads SET status='connected', connected_at=datetime('now') WHERE id=?",
                    (lead["id"],),
                )
                await log_activity(db, "connected", f"{lead['name']} accepted connection")
                await db.commit()

                # Send follow-up message
                first_name = lead["name"].split()[0]
                message = follow_up_template.replace("{name}", first_name)

                delay = random.uniform(min_delay, max_delay)
                await asyncio.sleep(delay)

                sent = await bot.send_message(url, message)
                if sent:
                    await db.execute(
                        "UPDATE leads SET status='messaged', message_sent_at=datetime('now') WHERE id=?",
                        (lead["id"],),
                    )
                    await db.execute(
                        "INSERT INTO messages(lead_id, body) VALUES (?,?)",
                        (lead["id"], message),
                    )
                    await log_activity(db, "message_sent", f"Sent follow-up to {lead['name']}")
                    await db.commit()
