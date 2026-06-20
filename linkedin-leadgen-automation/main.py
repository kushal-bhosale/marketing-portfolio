from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import json
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import init_db, DB_PATH
from linkedin import get_bot, shutdown_bot
from scheduler import run_connection_queue, run_acceptance_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Check for new connections every 30 minutes
    scheduler.add_job(run_acceptance_check, "interval", minutes=30, id="acceptance_check")
    scheduler.start()
    yield
    scheduler.shutdown()
    await shutdown_bot()


app = FastAPI(title="LinkedIn Bot", lifespan=lifespan)


# ── Models ──────────────────────────────────────────────────────────────────

class SearchFilters(BaseModel):
    keywords: str = ""
    title: str = ""
    location: str = ""
    network: list[str] = ["S"]  # Default: 2nd degree
    max_results: int = 30


class LeadAction(BaseModel):
    lead_ids: list[int]


class MessageTemplate(BaseModel):
    connection_message: str = ""
    follow_up_message: str = ""


class SettingsUpdate(BaseModel):
    daily_connection_limit: int = 15
    min_delay_seconds: int = 30
    max_delay_seconds: int = 90
    business_hours_start: int = 9
    business_hours_end: int = 18
    connection_message: str = ""
    follow_up_message: str = ""


# ── Debug ────────────────────────────────────────────────────────────────────

@app.get("/api/debug/page")
async def debug_page():
    """Return all /in/ links found on the current Chromium page."""
    bot = await get_bot()
    links = await bot._page.query_selector_all("a[href*='/in/']")
    hrefs = []
    for link in links:
        href = await link.get_attribute("href")
        text = (await link.inner_text()).strip()[:60]
        if href:
            hrefs.append({"href": href, "text": text})
    current_url = bot._page.url
    return {"current_url": current_url, "link_count": len(hrefs), "links": hrefs[:20]}


@app.get("/api/debug/extract")
async def debug_extract():
    """Run extraction on whatever page Chromium is currently on."""
    bot = await get_bot()
    current_url = bot._page.url
    leads = await bot._extract_leads_from_page()
    return {"current_url": current_url, "leads_found": len(leads), "leads": leads[:10]}


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/check")
async def check_auth():
    bot = await get_bot()
    logged_in = await bot.is_logged_in()
    return {"logged_in": logged_in}


@app.post("/api/auth/open-browser")
async def open_browser():
    """Open the browser so user can log in manually, then save cookies."""
    bot = await get_bot()
    await bot._page.goto("https://www.linkedin.com/login")
    return {"message": "Browser opened. Log in, then call /api/auth/save-cookies."}


@app.post("/api/auth/save-cookies")
async def save_cookies():
    bot = await get_bot()
    await bot.save_cookies()
    return {"message": "Cookies saved. You're authenticated for future runs."}


# ── Search ───────────────────────────────────────────────────────────────────

@app.post("/api/search")
async def search_leads(filters: SearchFilters):
    bot = await get_bot()
    if not await bot.is_logged_in():
        raise HTTPException(401, "Not logged in to LinkedIn")

    leads = await bot.search_people(filters.model_dump(), max_results=filters.max_results)

    # Save to DB with status 'pending' (not queued yet)
    async with aiosqlite.connect(DB_PATH) as db:
        for lead in leads:
            await db.execute(
                """INSERT OR IGNORE INTO leads
                   (linkedin_url, name, headline, company, location, profile_image, status)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    lead["linkedin_url"], lead["name"], lead["headline"],
                    lead["company"], lead["location"], lead["profile_image"], "pending"
                ),
            )
        await db.commit()

    return JSONResponse(content={"count": len(leads), "leads": leads})


# ── Leads ────────────────────────────────────────────────────────────────────

@app.get("/api/leads")
async def get_leads(status: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            async with db.execute(
                "SELECT * FROM leads WHERE status=? ORDER BY created_at DESC", (status,)
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM leads ORDER BY created_at DESC"
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]


@app.post("/api/leads/queue")
async def queue_leads(action: LeadAction):
    """Mark selected leads as queued for connection requests."""
    async with aiosqlite.connect(DB_PATH) as db:
        for lid in action.lead_ids:
            await db.execute(
                "UPDATE leads SET status='queued' WHERE id=? AND status='pending'", (lid,)
            )
        await db.commit()
    return {"queued": len(action.lead_ids)}


@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM leads WHERE id=?", (lead_id,))
        await db.commit()
    return {"deleted": lead_id}


# ── Manual triggers ───────────────────────────────────────────────────────────

@app.post("/api/run/connections")
async def trigger_connections(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_connection_queue)
    return {"message": "Connection queue started in background."}


@app.post("/api/run/check-acceptances")
async def trigger_acceptance_check(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_acceptance_check)
    return {"message": "Acceptance check started in background."}


# ── Settings ──────────────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT key, value FROM settings") as cur:
            rows = await cur.fetchall()
        return {r["key"]: r["value"] for r in rows}


@app.post("/api/settings")
async def save_settings(s: SettingsUpdate):
    data = s.model_dump()
    async with aiosqlite.connect(DB_PATH) as db:
        for k, v in data.items():
            await db.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (k, str(v))
            )
        await db.commit()
    return {"saved": True}


# ── Activity log ──────────────────────────────────────────────────────────────

@app.get("/api/activity")
async def get_activity(limit: int = 50):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, COUNT(*) as count FROM leads GROUP BY status"
        ) as cur:
            rows = await cur.fetchall()
        return {r["status"]: r["count"] for r in rows}


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def frontend():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
