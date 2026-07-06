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
        # All methods that navigate/interact with self._page share ONE
        # Playwright page (one visible browser tab). Without this lock, the
        # dashboard's periodic login-check (every 60s, and on every page
        # load) can call is_logged_in() — which navigates to /feed/ — at the
        # same moment a real action (search/connect/message) is mid-flight
        # on a profile page, yanking it away underneath that action. This
        # was confirmed live: a profile visit that should show a "Connect"
        # button intermittently got misread as "no Connect button found"
        # because the page had been navigated to /feed/ mid-check. Every
        # public method that touches self._page acquires this lock first so
        # actions are serialized instead of racing each other.
        self._page_lock = asyncio.Lock()

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
        async with self._page_lock:
            return await self._is_logged_in_locked()

    async def _is_logged_in_locked(self) -> bool:
        await self._page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        await short_delay()
        return "feed" in self._page.url

    async def search_people(self, filters: dict, max_results: int = 50) -> list[dict]:
        async with self._page_lock:
            return await self._search_people_locked(filters, max_results)

    async def _search_people_locked(self, filters: dict, max_results: int = 50) -> list[dict]:
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
        async with self._page_lock:
            return await self._send_connection_request_locked(linkedin_url, note)

    async def _send_connection_request_locked(self, linkedin_url: str, note: str = "") -> bool:
        """
        Visit a profile and click Connect. Optionally add a note (max 300 chars).
        Returns True on success.
        """
        try:
            await self._page.goto(linkedin_url, wait_until="domcontentloaded")
            await short_delay()

            # Wait for profile to fully load
            await asyncio.sleep(3)

            # Scroll to top to make sure profile action buttons are visible
            await self._page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(2)

            # Find the Connect button scoped to <main> only (excludes nav + sidebar)
            clicked = await self._page.evaluate("""() => {
                const nav   = document.querySelector('nav');
                const aside = document.querySelector('aside');

                function notHidden(el) {
                    // Use computed style — works even for fixed/sticky positioned elements
                    const s = window.getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
                }

                // Strategy: find leaf nodes with text "Connect" then walk up to
                // the nearest clickable ancestor. This works regardless of element type.
                function findClickableAncestor(el) {
                    let node = el.parentElement;
                    while (node && node !== document.body) {
                        if (aside && aside.contains(node)) return null; // in sidebar, skip
                        const tag  = node.tagName;
                        const role = (node.getAttribute('role') || '').toLowerCase();
                        if (tag === 'BUTTON' || tag === 'A' || role === 'button') return node;
                        node = node.parentElement;
                    }
                    return null;
                }

                // Find all leaf-level "Connect" text nodes (not in aside)
                const candidates = Array.from(document.querySelectorAll('span, div, li'))
                    .filter(el => {
                        if (aside && aside.contains(el)) return false;
                        return el.childElementCount === 0 && el.textContent.trim() === 'Connect';
                    });

                window._botButtons = candidates.map(el => ({
                    tag:     el.tagName,
                    text:    el.textContent.trim(),
                    inNav:   !!(nav   && nav.contains(el)),
                    inAside: !!(aside && aside.contains(el))
                }));

                for (const el of candidates) {
                    const clickable = findClickableAncestor(el);
                    if (clickable) {
                        clickable.click();
                        return 'direct:text-walk:' + clickable.tagName;
                    }
                }

                // Fallback: find "More" via text-walk — click BUTTON or A ancestor
                // LinkedIn's More button opens a dropdown (not a navigation) even as <A>
                //
                // IMPORTANT: the page can contain more than one "More" button (e.g. a
                // banner/promo card elsewhere on the page). The correct one lives inside
                // the profile intro card, so scope the search to that card only — found
                // via the nearest <section> ancestor of the profile's <h1> name heading.
                const main = document.querySelector('main');
                const h1 = main ? main.querySelector('h1') : null;
                const introCard = h1 ? (h1.closest('section') || main) : main;
                const searchRoot = introCard || document;

                const moreCandidates = Array.from(searchRoot.querySelectorAll('span, div, li'))
                    .filter(el => {
                        if (nav   && nav.contains(el))   return false;
                        if (aside && aside.contains(el)) return false;
                        return el.childElementCount === 0 && el.textContent.trim() === 'More';
                    });
                for (const el of moreCandidates) {
                    let node = el.parentElement;
                    while (node && node !== document.body) {
                        if (nav   && nav.contains(node))   break;
                        if (aside && aside.contains(node)) break;
                        const tag  = node.tagName;
                        const role = (node.getAttribute('role') || '').toLowerCase();
                        if (tag === 'BUTTON' || tag === 'A' || role === 'button') {
                            node.click();
                            return 'opened_more:' + tag;
                        }
                        node = node.parentElement;
                    }
                }
                return null;
            }""")

            # Log the buttons the bot saw (for debugging)
            btn_debug = await self._page.evaluate("() => window._botButtons || []")
            logger.info(f"Visible profile buttons: {btn_debug}")

            if clicked and clicked.startswith('opened_more'):
                # Wait up to 3s for the dropdown to render, then click Connect inside it
                await asyncio.sleep(2)
                # Use Playwright to find any clickable element whose text is "Connect"
                # that appeared after the dropdown opened (not in aside)
                connect_in_dropdown = await self._page.evaluate("""() => {
                    const aside = document.querySelector('aside');

                    // Dropdown menu items (e.g. "Send profile in a message", "Save to
                    // PDF", "Connect", "Report / Block") are role="menuitem"/"option"
                    // elements. They often contain a hidden accessibility-only span
                    // alongside the visible label, so they are NOT leaf nodes — match
                    // on the rendered `innerText` (visible text only) instead of
                    // `textContent` (which would include the hidden text too).
                    const items = Array.from(document.querySelectorAll(
                        '[role="menuitem"], [role="option"], li.artdeco-dropdown__item, ' +
                        'div.artdeco-dropdown__item'
                    ));
                    window._dropdownDebug = items.map(el => ({
                        tag:     el.tagName,
                        role:    el.getAttribute('role'),
                        text:    (el.innerText || '').trim().slice(0, 40),
                        inAside: !!(aside && aside.contains(el))
                    }));

                    // Match items whose VISIBLE text is exactly "Connect"
                    const match = items.find(el => {
                        if (aside && aside.contains(el)) return false;
                        const t = (el.innerText || '').trim().toLowerCase();
                        return t === 'connect';
                    });

                    if (match) {
                        match.click();
                        return 'dropdown_connect:' + match.tagName + ':' + (match.getAttribute('role') || '');
                    }
                    return null;
                }""")
                debug_info = await self._page.evaluate("() => window._dropdownDebug || []")
                logger.info(f"Dropdown Connect candidates: {debug_info}")
                if connect_in_dropdown:
                    clicked = connect_in_dropdown
                else:
                    clicked = None

            if not clicked:
                # Before giving up, check whether this profile already shows
                # "Pending" — meaning we (or the user, manually) already sent a
                # request earlier. That's a different situation from a genuine
                # Follow-only/no-button profile: it shouldn't be logged as a
                # "skip", it should be reconciled as already-requested.
                is_pending = await self._page.evaluate("""() => {
                    const aside = document.querySelector('aside');
                    const main = document.querySelector('main');
                    const h1 = main ? main.querySelector('h1') : null;
                    const introCard = h1 ? (h1.closest('section') || main) : main;
                    const root = introCard || document;
                    const nodes = Array.from(root.querySelectorAll('span, div, li, button'));
                    return nodes.some(el => {
                        if (aside && aside.contains(el)) return false;
                        if (el.childElementCount > 0) return false;
                        return el.textContent.trim() === 'Pending';
                    });
                }""")
                if is_pending:
                    logger.info(f"Profile already shows 'Pending' for {linkedin_url} — request was already sent previously")
                    return "already_pending"
                logger.warning(f"No Connect button found for {linkedin_url} — profile may use Follow-only mode")
                return False

            logger.info(f"Clicked: {clicked}")

            # Wait up to 10s for "Send without a note" button, then click it
            # if it's actually enabled.
            try:
                await self._page.wait_for_selector(
                    'button[aria-label="Send without a note"]',
                    timeout=10000
                )
                send_btn = await self._page.query_selector('button[aria-label="Send without a note"]')
                if send_btn:
                    # LinkedIn sometimes shows a variant of this same dialog that
                    # requires typing the person's email to "verify you know them"
                    # before allowing the invite — in that case "Send without a
                    # note" is present but disabled, and clicking it is a no-op.
                    if await send_btn.is_disabled():
                        logger.warning(f"'Send without a note' is disabled for {linkedin_url} — likely blocked by an email-verification gate")
                    else:
                        await send_btn.click()
            except Exception:
                # Timeout — dialog never appeared, request may have gone directly
                pass

            await asyncio.sleep(2)

            # Dismiss any lingering dialog (e.g. the email-verification gate)
            # so it doesn't block subsequent actions on this shared page.
            try:
                close_btn = await self._page.query_selector(
                    '[role="dialog"] button[aria-label="Dismiss"], .artdeco-modal button[aria-label="Dismiss"]'
                )
                if close_btn:
                    await close_btn.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

            # Don't trust any of the above heuristics on their own — LinkedIn's
            # dialog markup/timing for the email-verification gate has proven
            # inconsistent across attempts (sometimes no recognized dialog is
            # left to detect, even though the request never actually went
            # through). The only reliable signal is the profile itself: reload
            # it and check whether the intro card now shows "Pending" — the
            # exact same check already used above to detect a pre-existing
            # request. Only report success if this is confirmed.
            await self._page.goto(linkedin_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await self._page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(1)

            confirmed_pending = await self._page.evaluate("""() => {
                const aside = document.querySelector('aside');
                const main = document.querySelector('main');
                const h1 = main ? main.querySelector('h1') : null;
                const introCard = h1 ? (h1.closest('section') || main) : main;
                const root = introCard || document;
                const nodes = Array.from(root.querySelectorAll('span, div, li, button'));
                return nodes.some(el => {
                    if (aside && aside.contains(el)) return false;
                    if (el.childElementCount > 0) return false;
                    return el.textContent.trim() === 'Pending';
                });
            }""")

            if confirmed_pending:
                logger.info(f"Confirmed 'Pending' on {linkedin_url} after connect attempt — request genuinely sent")
                return True

            logger.warning(
                f"Profile for {linkedin_url} does NOT show 'Pending' after connect attempt — "
                f"request was likely blocked (e.g. an email-verification gate), not actually sent"
            )
            return "blocked_by_dialog"
        except Exception as e:
            logger.error(f"Error sending connection request: {e}")
            return False

    async def send_message(self, linkedin_url: str, message: str) -> bool:
        async with self._page_lock:
            return await self._send_message_locked(linkedin_url, message)

    async def _send_message_locked(self, linkedin_url: str, message: str) -> bool:
        """Send a DM to a connection."""
        try:
            await self._page.goto(linkedin_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)  # Wait for full render

            # The profile's "Message" element is an <a> with an EMPTY
            # aria-label (visible text only), so aria-label selectors never
            # match it. There are also decoy "Message" links elsewhere on
            # the page (suggested-profile widgets), so scope the search to
            # the profile's own intro card — found via the nearest
            # <section> ancestor of the profile's <h1> name heading — same
            # technique used for the More/Connect fix.
            #
            # Clicking that link raw does NOT open the messaging overlay
            # (confirmed live: zero DOM change, no new tab, no iframe
            # change). Instead, extract its href — LinkedIn's own
            # "/messaging/compose/?profileUrn=...&recipient=..." deep link
            # — and navigate to it directly, which reliably opens the
            # compose overlay.
            href = await self._page.evaluate("""() => {
                const nav = document.querySelector('nav');
                const main = document.querySelector('main');
                const h1 = main ? main.querySelector('h1') : null;
                const introCard = h1 ? (h1.closest('section') || main) : main;
                const candidates = Array.from(introCard.querySelectorAll('span, div, li, a'))
                    .filter(el => {
                        if (nav && nav.contains(el)) return false;
                        return el.childElementCount === 0 && el.textContent.trim() === 'Message';
                    });
                for (const el of candidates) {
                    let node = el.parentElement;
                    while (node && node !== document.body) {
                        if (node.tagName === 'A' && node.getAttribute('href')) {
                            return node.getAttribute('href');
                        }
                        node = node.parentElement;
                    }
                }
                return null;
            }""")

            if not href:
                logger.warning(f"No Message link for {linkedin_url}")
                return False

            compose_url = "https://www.linkedin.com" + href if href.startswith("/") else href
            await self._page.goto(compose_url, wait_until="domcontentloaded")
            # The messaging overlay loads minimized and takes a few seconds
            # to render the compose textbox — a short sleep isn't enough.
            await asyncio.sleep(7)

            msg_box = await self._page.query_selector("div.msg-form__contenteditable")
            if not msg_box:
                logger.warning(f"Message box did not appear for {linkedin_url}")
                return False

            await msg_box.click()

            # IMPORTANT: don't type the raw message string in one go if it
            # contains "\n". LinkedIn's compose box treats a plain Enter
            # keypress as "send" (Shift+Enter for a line break) — same as
            # Slack/most chat UIs. Typing an embedded "\n" character via
            # .type() fires a real Enter keypress, which was triggering a
            # premature/partial send mid-typing and leaving the page in a
            # broken state (confirmed live: caused an unrecoverable hang
            # with no exception, and the tab drifted off the compose
            # overlay). Fix: type each line separately and insert line
            # breaks explicitly via Shift+Enter.
            lines = message.split("\n")
            for i, line in enumerate(lines):
                if line:
                    await msg_box.type(line, delay=random.uniform(20, 50))
                if i < len(lines) - 1:
                    await self._page.keyboard.press("Shift+Enter")
            await short_delay()

            send_btn = await self._page.query_selector(
                "button.msg-form__send-button[type='submit']"
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
        async with self._page_lock:
            return await self._check_new_connections_locked()

    async def _check_new_connections_locked(self) -> list[str]:
        """
        Check the My Network page for recently accepted connections.
        Returns list of profile URLs.
        """
        try:
            await self._page.goto(
                "https://www.linkedin.com/mynetwork/invite-connect/connections/",
                wait_until="domcontentloaded",
            )
            await asyncio.sleep(3)

            # Extract all /in/ profile links on the connections page
            # LinkedIn changes class names often — use href pattern instead
            urls = await self._page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a[href*="/in/"]'));
                const seen = new Set();
                const results = [];
                for (const link of links) {
                    const href = link.href || '';
                    const match = href.match(/linkedin\\.com(\\/in\\/[^/?#]+)/);
                    if (!match) continue;
                    const path = match[1].replace(/\\/$/, '');
                    if (seen.has(path)) continue;
                    seen.add(path);
                    results.push('https://www.linkedin.com' + path);
                }
                return results;
            }""")
            logger.info(f"check_new_connections: found {len(urls)} profiles on connections page")
            return urls
        except Exception as e:
            logger.error(f"Error checking connections: {e}")
            return []


# Global singleton reused across requests
_bot: LinkedInBot | None = None
_bot_lock = asyncio.Lock()

async def get_bot() -> LinkedInBot:
    global _bot
    # Guard against concurrent callers (e.g. two open browser tabs both
    # firing checkAuth() on load) racing to init the bot — without this,
    # a second caller could see `_bot` already assigned but `start()`
    # not yet finished, and hit `self._page` while it's still None.
    async with _bot_lock:
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
