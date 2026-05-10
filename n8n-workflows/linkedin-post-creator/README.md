# AI-Powered LinkedIn Content Workflow

An automated n8n workflow that pulls relevant industry news, filters it using AI, and generates LinkedIn-ready posts in a specific human voice — delivered to your inbox daily.

---

## What it does

Runs on a schedule. No manual input needed.

1. Fetches articles from a Google News RSS feed targeting B2B startup and AI marketing content
2. Parses the XML feed and extracts article titles and URLs
3. Sends articles to GPT-4o to filter the 2 most relevant ones for the target audience
4. Pulls persona data (voice rules, content pillars, audience, role) from a Notion database
5. Merges everything into a single clean item via a Code node
6. Sends the merged data to GPT-4o to write a LinkedIn post in the defined voice
7. Delivers the post to your Gmail inbox for light editing before publishing

---

## Target audience

Early-stage B2B SaaS founders and startup founders building one-person marketing functions with AI.

---

## Content pillars

- Building messaging and positioning that differentiates your brand
- One-person marketing team with agentic AI
- Cross-functional team alignment in marketing

---

## Workflow architecture

```
Schedule Trigger
    → HTTP Request (Google News RSS)
        → XML (parse to JSON)
            → Limit
                → OpenAI GPT-4o (filter 2 relevant articles → JSON array)
                    → Notion (get persona: voice, audience, pillars, role)
                        → Merge (append mode)
                            → Code node (consolidate into 1 item)
                                → OpenAI GPT-4o (write LinkedIn post)
                                    → Gmail (send to inbox)
```

---

## Node breakdown

| Node | Purpose |
|---|---|
| Schedule Trigger | Runs workflow on a set cadence |
| HTTP Request | Fetches Google News RSS feed |
| XML | Converts RSS XML to JSON |
| Limit | Caps items to avoid token overload |
| OpenAI #1 (Message a model) | Filters 2 most relevant articles, returns JSON array with title, summary, url |
| Notion (Get many database pages) | Pulls persona config: system prompt, voice DNA, audience, content pillars, channel, role |
| Merge | Appends Notion data and OpenAI output into one stream |
| Code | Finds Notion item and article item, merges into single clean JSON object |
| OpenAI #2 (Message a model1) | Writes LinkedIn post using persona config and filtered articles |
| Gmail | Sends finished post to inbox |

---

## Notion database schema

The workflow reads from a Notion database with the following properties:

| Field | Description |
|---|---|
| `property_name` | Author name (Kushal Bhosale) |
| `property_role` | Professional role |
| `property_audience` | Target audience definition |
| `property_channel` | Publishing channel (LinkedIn) |
| `property_content_pillars` | 3 content focus areas |
| `property_system_prompt` | Full system prompt including voice sample |
| `property_avoid` | Voice DNA: banned words, phrases, patterns |
| `property_tone` | Tone descriptor |
| `property_active` | Toggle to pause/resume workflow |

---

## Voice DNA (summary)

The output is governed by a detailed writing ruleset stored in Notion. Key rules:

- Short paragraphs, 1-2 sentences default
- No em dashes, no filler phrases, no hype language
- Write in first person, direct address, active voice
- Banned: "leverage," "scalable," "seamless," "game-changer" and ~60 other AI-fingerprint words
- Banned structures: negative parallelisms ("It's not X, it's Y"), engagement bait, metronome rhythm
- End posts with a sharp, specific question tied to the article's insight

---

## RSS feed

```
https://news.google.com/rss/search?q=AI+marketing+B2B+startup&hl=en-IN&gl=IN&ceid=IN:en
```

Swap keywords to shift content focus. Additional sources to add later: SaaStr, a16z, First Round Review.

---

## Key prompts

**Article filter prompt (OpenAI #1)**
```
You are a content filter for a newsletter. From the articles below, pick the 2 most
relevant for B2B startup founders and investors setting up one-person marketing
functions using AI. Summarise each in 3 bullet points. Return ONLY a JSON array
with keys: title, summary, url. No extra text, no markdown, no code blocks.
```

**Post writer prompt (OpenAI #2)**

Dynamically assembled from Notion fields:
- System prompt + voice DNA
- Audience, content pillars, channel, role
- Filtered articles from OpenAI #1
- Instruction: 150-200 words, hook on first line, 2-4 lines of insight, sharp closing question, no CTA, no hashtags

---

## Sample output

> Gushwork just raised $9 million to scale AI-driven marketing for lean B2B SaaS teams.
>
> Founders often think marketing means hiring a big team or dropping cash on agencies. I've seen startups burn $5-10k a month on generic content that doesn't move the needle. The real win comes from 1 person who knows the product, paired with AI that handles distribution and routine work.
>
> This keeps marketing lean, close to the product, and focused on the positioning that actually sticks.
>
> Does your marketing feel like it's guessing, or is it tied to what your customers actually say?

---

## What broke along the way (and how it was fixed)

**Telegram bot not working**
Switched to Gmail. Bot wasn't receiving messages due to a likely webhook conflict; `deleteWebhook` confirmed nothing was set. Pivoted to Gmail which worked immediately.

**Gemini credits ran out**
Switched to OpenAI GPT-4o-mini mid-build, then upgraded to GPT-4o for better instruction-following on complex voice rules.

**RSS feed passing channel metadata instead of articles**
Articles were nested at `rss.channel.item`. Fixed the expression to `item.json.rss.channel.item` to reach the actual article array.

**Notion node returning only id, name, url**
Was using "Get Database" operation which returns metadata only. Switched to "Get Many Database Pages" which returns full properties.

**Merge node mixing items**
n8n's expression editor evaluates against the current item, so cross-referencing items via `$input.item(0)` in the prompt field was unreliable. Fixed by adding a Code node that consolidates everything into 1 clean item before the final OpenAI node.

**Output violating Voice DNA rules**
GPT-4o-mini couldn't follow the long ruleset reliably. Switched to GPT-4o and added a CRITICAL CHECK reminder inside the prompt. Output quality improved significantly.

---

## To activate

Toggle the workflow from **Inactive → Active** in the n8n canvas. It will run on the configured schedule automatically.

---

## Planned improvements

- Add multiple RSS sources (SaaStr, a16z, First Round Review, Reddit r/SaaS)
- Use `property_active` field in Notion as a filter node to pause per-persona without touching the workflow
- Add Slack delivery as an alternative to Gmail
- Explore LinkedIn API or Zapier integration for direct publishing
