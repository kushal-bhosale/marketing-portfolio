from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import csv
import io
import json
import re
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


# ── Apollo CSV import helpers ────────────────────────────────────────────────
# Apollo's export column names have shifted across versions ("Person Linkedin
# Url" vs "LinkedIn Url", etc.), so match on a normalized (lowercased,
# punctuation/space-stripped) header against a list of known aliases rather
# than requiring an exact column name.

_APOLLO_ALIASES = {
    "linkedin_url": ["personlinkedinurl", "linkedinurl", "linkedin", "personlinkedin", "liurl", "profileurl"],
    "first_name": ["firstname"],
    "last_name": ["lastname"],
    "full_name": ["name", "fullname", "personname"],
    "email": ["email", "emailaddress", "workemail"],
    "title": ["title", "jobtitle", "headline", "persontitle"],
    "company": ["company", "companyname", "organization", "organizationname", "account", "accountname"],
    "city": ["city", "personcity"],
    "state": ["state", "personstate"],
    "country": ["country", "personcountry"],
    "location": ["location"],
}


def _normalize_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def _get_field(normalized_row: dict, key: str) -> str:
    for alias in _APOLLO_ALIASES[key]:
        val = normalized_row.get(alias, "")
        if val and val.strip():
            return val.strip()
    return ""


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


@app.get("/api/debug/goto")
async def debug_goto(url: str):
    """Navigate the bot's live browser to an arbitrary URL, for live diagnostics
    (e.g. inspect a specific profile that misbehaved)."""
    bot = await get_bot()
    async with bot._page_lock:
        await bot._page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        return {"current_url": bot._page.url}


@app.get("/api/debug/buttons")
async def debug_buttons():
    """Dump all buttons on the current Chromium page."""
    bot = await get_bot()
    async with bot._page_lock:
        buttons = await bot._page.evaluate("""() => {
            const btns = document.querySelectorAll('button, div[role="button"], a[role="button"]');
            return Array.from(btns).map(b => ({
                tag: b.tagName,
                label: b.getAttribute('aria-label') || '',
                text: b.innerText.trim().slice(0, 60),
                visible: b.offsetParent !== null
            })).filter(b => b.label || b.text);
        }""")
        return {"url": bot._page.url, "buttons": buttons}


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


@app.post("/api/leads/upload")
async def upload_leads(file: UploadFile = File(...)):
    """Bulk-import leads from an Apollo (or similar) CSV export.

    Rows without a LinkedIn URL are skipped (the leads table is keyed on
    linkedin_url). If a row's LinkedIn URL already exists as a lead (e.g.
    found earlier via Search), we only backfill its email if missing —
    status/history on the existing lead is left untouched.
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "Could not read any columns from this file — is it a CSV export?")

    imported = 0
    updated_email = 0
    skipped_duplicate = 0
    skipped_no_url = 0

    async with aiosqlite.connect(DB_PATH) as db:
        for row in reader:
            normalized_row = {_normalize_header(k): (v or "") for k, v in row.items() if k}

            linkedin_url = _get_field(normalized_row, "linkedin_url")
            if not linkedin_url:
                skipped_no_url += 1
                continue

            name = _get_field(normalized_row, "full_name")
            if not name:
                name = f"{_get_field(normalized_row, 'first_name')} {_get_field(normalized_row, 'last_name')}".strip()

            email = _get_field(normalized_row, "email")
            headline = _get_field(normalized_row, "title")
            company = _get_field(normalized_row, "company")
            location = _get_field(normalized_row, "location")
            if not location:
                parts = [_get_field(normalized_row, k) for k in ("city", "state", "country")]
                location = ", ".join(p for p in parts if p)

            async with db.execute(
                "SELECT id, email FROM leads WHERE linkedin_url=?", (linkedin_url,)
            ) as cur:
                existing = await cur.fetchone()

            if existing:
                lead_id, existing_email = existing
                if email and not existing_email:
                    await db.execute("UPDATE leads SET email=? WHERE id=?", (email, lead_id))
                    updated_email += 1
                else:
                    skipped_duplicate += 1
            else:
                await db.execute(
                    """INSERT INTO leads
                       (linkedin_url, name, headline, company, location, email, status, source)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (linkedin_url, name, headline, company, location, email, "pending", "apollo"),
                )
                imported += 1

        await db.commit()

    return {
        "imported": imported,
        "updated_email": updated_email,
        "skipped_duplicate": skipped_duplicate,
        "skipped_no_linkedin_url": skipped_no_url,
    }


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


@app.post("/api/leads/reset")
async def reset_leads():
    """Reset all ignored/failed leads back to pending for re-testing."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE leads SET status='pending' WHERE status IN ('ignored', 'queued', 'requested')"
        )
        await db.commit()
    return {"reset": True}


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
    # Safari (unlike Chrome) will happily serve a stale cached copy of this
    # page even on a brand-new tab/window, since we never told it not to.
    # Force no caching so every load always gets the current file.
    return FileResponse(
        "static/index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
