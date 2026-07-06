# LinkedIn Lead Gen Automation

A lightweight Phantombuster alternative built for personal use. Automates LinkedIn prospecting — from finding leads to sending connection requests to following up when they accept.

## What it does

1. **Search for leads** — Filter by job title, keywords, location, and network degree (1st, 2nd, 3rd+)
2. **Import from Apollo** — Bulk-upload an Apollo contact-list CSV export (matched by LinkedIn URL) to feed leads sourced outside LinkedIn search into the same pipeline
3. **Queue connection requests** — Select leads from the list and schedule connection requests with human-like delays
4. **Auto follow-up** — Detects when someone accepts your request and sends a personalised follow-up message automatically

## Stack

- **Python + FastAPI** — Backend API and scheduling
- **Playwright** — Browser automation (runs in your real Chrome session, not a headless bot)
- **SQLite** — Stores leads, statuses, and activity logs
- **HTML/JS** — Simple web UI served locally at `http://localhost:8000`

## Safety features

- Hard daily limit (default: 15 connection requests/day)
- Randomised delays between actions (30–90 seconds)
- Business hours only (9am–6pm)
- Uses your real browser session via cookies — not a headless bot

## Setup

```bash
bash setup.sh
source venv/bin/activate
python main.py
```

Then open `http://localhost:8000` in your browser.

**First run:** Click "Open Browser", log into LinkedIn, then click "Save Session" to save your cookies.

## Usage

1. **Search tab** — Enter job title, keywords, network degree → click Search
2. **Leads tab** — Select people you want to connect with → Queue Selected
3. Click **Run Connection Queue Now** or let it run automatically every 30 min
4. **Connected tab** — See who accepted; follow-up messages go out automatically
5. **Settings tab** — Customise rate limits and message templates

## Disclaimer

This tool is for personal use only. Use responsibly and within LinkedIn's usage limits. Running at low volumes (15 req/day with delays) significantly reduces detection risk, but automation always carries some account risk.
