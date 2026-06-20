"""
LinkedIn browser automation via Playwright.
Uses a saved cookie session so LinkedIn sees your real browser.
"""
from __future__ import annotations
import asyncio
import json
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)

COOKIES_PATH = Path("linkedin_cookies.json")
HEADLESS = False  # Keep visible so LinkedIn sees real browser behaviour


async def human_delay(min_s: float = 30, max_s: float = 90):
    """Random delay to mimic human pacing."""
    delay = random.uniform(min_s, max_s)
    logger.info(f"Waiting {delay:.1f}s...")
    await asyncio.sleep(delay)


async def short_delay():
    """Short delay between UI interactions (0.5–2.5s)."""
    await asyncio.sleep(random.uniform(0.5, 2.5))


class LinkedInBot:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        if COOKIES_PATH.exists():
            cookies = json.loads(COOKIES_PATH.read_text())
            await self._context.add_cookies(cookies)
        self._page = await self._context.new_page()

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def save_cookies(self):
        if self._context:
            cookies = await self._context.cookies()
            COOKIES_PATH.write_text(json.dumps(cookies, indent=2))

    async def is_logged_in(self) -> bool:
        await self._page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await short_delay()
        return "feed" in self._page.url

    async def search_people(self, filters: dict, max_results: int = 50) -> list[dict]:
        """
        Search LinkedIn people with filters:
          keywords, title, company, location, industry, network (F=1st, S=2nd, O=3rd+)
        Returns list of lead dicts.
        """
        params = self._build_search_params(filters)
        url = f"https://www.linkedin.com/search/results/people/?{params}"
        leads = []
        page_num = 1

        while len(leads) < max_results:
            paginated = url + f"&page={page_num}"
            await self._page.goto(paginated, wait_until="domcontentloaded")
            await asyncio.sleep(3)  # Let JS render

            # Wait for any profile link to appear
            try:
                await self._page.wait_for_selector(
                    "a[href*='/in/']",
                    timeout=12000,
                )
            except Exception:
                logger.warning("No profile links found on page — stopping.")
                break

            page_leads = await self._extract_leads_from_page()
            if not page_leads:
                break

            for lead in page_leads:
                if lead["linkedin_url"] not in {l["linkedin_url"] for l in leads}:
                    leads.append(lead)
                if len(leads) >= max_results:
                    break

            if len(leads) >= max_results:
                break

            # Check if there's a next page
            next_btn = await self._page.query_selector("button[aria-label='Next']")
            if not next_btn:
                break

            page_num += 1
            await short_delay()

        return leads[:max_results]

    async def _extract_leads_from_page(self) -> list:
        """Extract all people from the current search results page."""
        # Scroll down to trigger lazy loading of results
        await self._page.evaluate("window.scrollTo(0, 600)")
        await asyncio.sleep(2)
        await self._page.evaluate("window.scrollTo(0, 1200)")
        await asyncio.sleep(1)

        # Use JavaScript to extract all lead data in one shot
        leads_raw = await self._page.evaluate("""() => {
            const results = [];
            const seen = new Set();

            const links = document.querySelectorAll('a[href*="/in/"]');

            for (const link of links) {
                const href = link.href || '';
                const match = href.match(/linkedin\\.com\\/in\\/([^/?#]+)/);
                if (!match) continue;
                const slug = match[1];
                if (!slug || seen.has(slug)) continue;

                // ── Get link's own text (the name link is SHORT — just the name)
                const linkText = link.innerText.trim();

                // Skip links with long text (these are card-wrapper links, not name links)
                // Skip links with no text (image-only links)
                // A real name is < 60 chars and doesn't contain "Follow"/"Connect"/"mutual"
                if (linkText.length > 60) continue;
                if (linkText.length < 2) continue;
                if (/follow|connect|mutual|message|view profile/i.test(linkText)) continue;

                const name = linkText.replace(/\\s+/g, ' ').trim();
                seen.add(slug);

                // ── Walk up to find the card container, then grab its full text
                let card = link.parentElement;
                let cardText = '';
                let image = '';
                for (let i = 0; i < 12; i++) {
                    if (!card) break;
                    const t = card.innerText || '';
                    // Card text should include the name and be reasonably long
                    if (t.includes(name) && t.length > 80) {
                        cardText = t;
                        // Try multiple image selectors
                        const imgEl = card.querySelector(
                            'img[src*="licdn"], img[src*="media.licdn"], ' +
                            'img[src*="profile-displayphoto"], img[src*="profile-framedphoto"]'
                        );
                        if (imgEl) image = imgEl.src;
                        break;
                    }
                    card = card.parentElement;
                }

                // ── Parse headline & location from card text
                // Pattern: "Name [badge] Name • 2nd HEADLINE\\nLOCATION\\nFollow..."
                let headline = '', location = '';
                const bulletIdx = cardText.indexOf('•');
                if (bulletIdx !== -1) {
                    const afterBullet = cardText.slice(bulletIdx + 1)
                        .replace(/^\\s*(1st|2nd|3rd\\+?)\\s*/, '').trim();
                    const lines = afterBullet.split('\\n')
                        .map(l => l.trim())
                        .filter(l => l.length > 1 &&
                            !/^(follow|connect|message|skills:|current:|\\d+\\s*follower)/i.test(l));
                    if (lines[0]) headline = lines[0];
                    if (lines[1] && lines[1].length < 60) location = lines[1];
                }

                results.push({
                    name,
                    linkedin_url: 'https://www.linkedin.com/in/' + slug,
                    headline,
                    location,
                    company: '',
                    profile_image: image
                });
            }
            return results;
        }""")

        def fix_encoding(s: str) -> str:
            """Fix UTF-8 text that was misread as Latin-1 by Playwright."""
            if not s:
                return s
            try:
                return s.encode("latin-1").decode("utf-8")
            except Exception:
                return s

        # Filter out duplicates and mutual connections
        # Mutual connections appear in other people's cards and share
        # the exact same headline + location as the main result person.
        seen_urls = set()
        seen_card_signatures = set()
        leads = []
        for lead in leads_raw:
            url = lead.get("linkedin_url", "")
            if not url or url in seen_urls:
                continue

            # If headline+location combo was already seen, this is a mutual
            # connection listed inside another person's card — skip it.
            headline = lead.get("headline", "").strip()
            location = lead.get("location", "").strip()
            if headline and location:
                sig = f"{headline}||{location}"
                if sig in seen_card_signatures:
                    continue
                seen_card_signatures.add(sig)

            seen_urls.add(url)
            # Fix encoding on all text fields
            lead["name"] = fix_encoding(lead.get("name", ""))
            lead["headline"] = fix_encoding(lead.get("headline", ""))
            lead["location"] = fix_encoding(lead.get("location", ""))
            lead["company"] = fix_encoding(lead.get("company", ""))
            leads.append(lead)

        logger.info(f"Extracted {len(leads)} leads from page")
        return leads

    def _build_search_params(self, filters: dict) -> str:
        from urllib.parse import quote

        parts = []

        # Keywords: title + freetext keywords only (NOT location)
        keyword_parts = []
        if filters.get("title"):
            keyword_parts.append(filters["title"])
        if filters.get("keywords"):
            keyword_parts.append(filters["keywords"])
        if keyword_parts:
            parts.append("keywords=" + quote(" ".join(keyword_parts)))

        # Network filter — LinkedIn expects network=["S"] properly encoded
        # %5B = [   %22 = "   %2C = ,   %5D = ]
        if filters.get("network"):
            codes = filters["network"]
            inner = "%2C".join('%22' + c + '%22' for c in codes)
            parts.append("network=%5B" + inner + "%5D")

        # Note: LinkedIn free doesn't support location filtering via URL
        # without a private geoUrn ID. Location is shown in results so
        # you can still see and filter manually.

        parts.append("origin=GLOBAL_SEARCH_HEADER")
        return "&".join(parts)


    async def send_connection_request(self, linkedin_url: str, note: str = "") -> bool:
        """
        Visit a profile and click Connect. Optionally add a note (max 300 chars).
        Returns True on success.
        """
        try:
            await self._page.goto(linkedin_url, wait_until="domcontentloaded")
            await short_delay()

            # Find Connect button — may be inside "More" menu
            connect_btn = await self._page.query_selector(
                "button[aria-label*='Connect']"
            )
            if not connect_btn:
                # Try More actions menu
                more_btn = await self._page.query_selector(
                    "button[aria-label*='More actions']"
                )
                if more_btn:
                    await more_btn.click()
                    await short_delay()
                    connect_btn = await self._page.query_selector(
                        "div[aria-label*='Connect'], span:has-text('Connect')"
                    )

            if not connect_btn:
                logger.warning(f"No Connect button found for {linkedin_url}")
                return False

            await connect_btn.click()
            await short_delay()

            if note:
                # Click "Add a note"
                add_note_btn = await self._page.query_selector(
                    "button[aria-label='Add a note']"
                )
                if add_note_btn:
                    await add_note_btn.click()
                    await short_delay()
                    textarea = await self._page.query_selector(
                        "textarea[name='message']"
                    )
                    if textarea:
                        await textarea.fill(note[:300])
                        await short_delay()

            # Click Send / Done
            send_btn = await self._page.query_selector(
                "button[aria-label='Send now'], button[aria-label='Send invitation']"
            )
            if send_btn:
                await send_btn.click()
                await short_delay()
                logger.info(f"Connection request sent to {linkedin_url}")
                return True

            return False
        except Exception as e:
            logger.error(f"Error sending connection request: {e}")
            return False

    async def send_message(self, linkedin_url: str, message: str) -> bool:
        """Send a DM to a connection."""
        try:
            await self._page.goto(linkedin_url, wait_until="domcontentloaded")
            await short_delay()

            msg_btn = await self._page.query_selector(
                "button[aria-label*='Message']"
            )
            if not msg_btn:
                logger.warning(f"No Message button for {linkedin_url}")
                return False

            await msg_btn.click()
            await short_delay()

            # Type into message box
            msg_box = await self._page.query_selector(
                "div[role='textbox'][aria-label*='message'], "
                ".msg-form__contenteditable"
            )
            if not msg_box:
                return False

            await msg_box.click()
            await msg_box.type(message, delay=random.uniform(30, 80))
            await short_delay()

            send_btn = await self._page.query_selector(
                "button[type='submit'][aria-label*='Send'], "
                ".msg-form__send-button"
            )
            if send_btn:
                await send_btn.click()
                await short_delay()
                logger.info(f"Message sent to {linkedin_url}")
                return True

            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def check_new_connections(self) -> list[str]:
        """
        Check the My Network page for recently accepted connections.
        Returns list of profile URLs.
        """
        try:
            await self._page.goto(
                "https://www.linkedin.com/mynetwork/invite-connect/connections/",
                wait_until="domcontentloaded",
            )
            await short_delay()

            cards = await self._page.query_selector_all(
                "li.mn-connection-card"
            )
            urls = []
            for card in cards:
                link = await card.query_selector("a.mn-connection-card__link")
                if link:
                    href = await link.get_attribute("href")
                    if href and "/in/" in href:
                        urls.append("https://www.linkedin.com" + href.split("?")[0].rstrip("/"))
            return urls
        except Exception as e:
            logger.error(f"Error checking connections: {e}")
            return []


# Global singleton reused across requests
_bot: LinkedInBot | None = None

async def get_bot() -> LinkedInBot:
    global _bot
    if _bot is None:
        _bot = LinkedInBot()
        await _bot.start()
    return _bot

async def shutdown_bot():
    global _bot
    if _bot:
        await _bot.save_cookies()
        await _bot.stop()
        _bot = None
