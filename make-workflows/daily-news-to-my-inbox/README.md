# Daily Fintech News — Make Automation

Automated daily digest of Indian BFSI/Fintech news, summarized by AI and delivered to your inbox every morning.

## What it does

1. **Fetches RSS** — Pulls up to 10 articles from the past 24 hours via Google News RSS, filtered for keywords: `lending`, `wealth`, `fintech`, `NBFC` + `India`
2. **Aggregates headlines** — Collates all article titles and URLs into a single text block
3. **AI Summary** — Sends the list to Gemini 2.5 Flash-Lite, which returns:
   - A 3-sentence executive summary of the biggest trends
   - Top 5 must-read stories with a one-line "why it matters" and clickable URLs
4. **Email delivery** — Sends the formatted digest via Gmail to the configured recipient

## Automation flow

```
RSS Feed (Google News)
    → Text Aggregator
        → Gemini 2.5 Flash-Lite
            → Gmail (daily digest email)
```

## Make modules used

| Step | Module |
|------|--------|
| RSS Fetch | `rss:ActionReadArticles` |
| Aggregation | `util:TextAggregator` |
| AI Summary | `gemini-ai:createACompletionGeminiPro` |
| Email | `google-email:sendAnEmail` |

## RSS query

```
https://news.google.com/rss/search?q=intitle:(lending+OR+wealth+OR+fintech+OR+NBFC)+India+when:1d&hl=en-IN&gl=IN&ceid=IN:en
```

## Gemini system prompt

> You are an expert marketing strategist specializing in Indian Fintech and BFSI. Your goal is to provide high-signal, insight-driven summaries of daily news. Avoid fluff and promotional language. Focus on market gaps, regulatory changes (like UPI/BBPS updates if relevant), and institutional shifts.

## How to import

1. Open [Make.com](https://make.com) and go to **Scenarios**
2. Click **Create a new scenario** → **Import Blueprint**
3. Upload `Daily Fintech News_RSS.blueprint.json`
4. Reconnect your own **Gemini AI** and **Gmail** connections (the imported blueprint will have broken connection references)
5. Set your schedule to run daily at 7 AM

## Requirements

- Make.com account
- Google Gemini API connection (Gemini AI app in Make)
- Gmail connection (Google Email app in Make)
