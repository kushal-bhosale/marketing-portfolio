# AI-Powered LinkedIn Content Workflow

An automated n8n workflow that pulls multi-source industry news, deduplicates against past sends, generates a LinkedIn rough draft, and delivers it to your inbox daily. Final voice polish happens in a separate Claude voice project before publishing.

## What it does

Runs daily at 7 AM IST. No manual input needed.

1. Fetches articles from 5 Google News RSS feeds (all scoped to last 24 hours via `when:1d`)
2. Normalises URLs, hashes titles, and deduplicates within today's pull
3. Checks every candidate against a Notion "Sent Articles" database (past 7 days)
4. If anything fresh remains: Gemini picks the best fit for the content pillars, actively avoiding recent topics
5. Gemini writes a rough draft + a short subject line angle (returned as JSON)
6. Sends the draft to your Gmail inbox with the format `LI Draft [DD MMM] — <angle>`
7. Logs the picked article to the Sent Articles DB so tomorrow's run won't repeat it
8. If everything in today's pull is a dupe, sends a "no fresh content today" email instead

## Workflow design philosophy

The system is split into three layers, each doing what it's good at:

| Layer | Job | Tool |
|---|---|---|
| n8n + Gemini Flash (Pick) | Classify which article fits the content pillars | Cheap, fast, good at structured tasks |
| n8n + Gemini Flash (Write) | Produce a structurally correct rough draft with the right ICP angle | Handles the boring frame |
| Claude voice project | Apply full Voice DNA, scrub AI tics, final polish | Long-instruction-following, taste |

The n8n output is a **research note, not a publish-ready post**. Treating it as a draft to forward leads to generic copy. Treating it as raw material for the voice project leads to sharp posts.

## Target audience

LinkedIn audience is split between:
1. Early-stage B2B SaaS founders
2. Founders / marketers building one-person marketing functions with AI

## Content pillars

1. Messaging and positioning that differentiates B2B brands
2. One-person marketing teams powered by agentic AI
3. Cross-functional alignment (marketing × product × sales)

## Workflow architecture

```
Schedule Trigger (7 AM IST)
    → Define RSS Feeds (5 sources)
        → Split Into Feeds
            → Fetch RSS (per feed)
                → Parse XML
                    → Split Into Articles
                        → Normalise Articles (clean URL, title hash)
                            → Collect All Articles
                                → Dedupe Today's Pull
                                    ├─→ Get Sent History (Notion, last 7 days)
                                    └─→ Filter Out Already Sent
                                        → Any Fresh Articles? (IF node)
                                            ├─ NO → Send "No Content" Email
                                            └─ YES → Get Persona (Notion)
                                                → Pick Best Article (Gemini)
                                                    → Parse Pick
                                                        → Write Post (Gemini)
                                                            → Parse Post (extract subject + body JSON)
                                                                → Send Post Email (Gmail)
                                                                    → Log to Sent Articles DB (Notion)
```

## Node breakdown

| Node | Purpose |
|---|---|
| Schedule Trigger | Fires daily at 7 AM |
| Define RSS Feeds | Holds the list of 5 Google News URLs |
| Split Into Feeds | One execution per feed |
| Fetch RSS | HTTP GET on each feed URL |
| Parse XML | RSS XML → JSON |
| Split Into Articles | Each article becomes its own item |
| Normalise Articles | Strips query params, lowercases URL, builds title-key hash |
| Collect All Articles | Aggregates articles from all 5 feeds |
| Dedupe Today's Pull | Removes duplicates across feeds (by URL + title hash) |
| Get Sent History | Pulls past 7 days of sent posts from Notion |
| Filter Out Already Sent | Removes candidates that match history |
| Any Fresh Articles? | IF node — branches to write flow or "no content" email |
| Get Persona | Pulls system_prompt, audience, pillars, voice rules from Notion |
| Pick Best Article | Gemini picks one article, told to diversify from recent topics |
| Parse Pick | Cleans Gemini JSON output, cross-references against fresh list |
| Write Post | Gemini drafts the post + subject line as JSON |
| Parse Post | Strips code fences, adds `LI Draft [DD MMM]` prefix to subject |
| Send Post Email | Gmail delivery |
| Send "No Content" Email | Failsafe when everything is a dupe |
| Log to Sent Articles DB | Creates a row so tomorrow knows what's been sent |

## RSS feeds

All scoped to the last 24 hours via the `when:1d` Google News parameter.

| Feed | Query |
|---|---|
| AI Marketing B2B | `AI marketing B2B startup` |
| Solo Marketing Function | `"one person marketing" OR "solo marketer" OR "lean marketing team"` |
| Marketing Automation Startups | `marketing automation early stage startup` |
| B2B GTM Growth | `B2B GTM OR "go to market" startup growth` |
| AI Tools for Marketers | `"AI tools" marketers OR "AI for marketing"` |

Swap or add queries in the `Define RSS Feeds` node.

## Notion databases

### Personas DB

Stores the writing config. The workflow reads one row.

| Property | Type | Purpose |
|---|---|---|
| name | Title | Persona name |
| role | Text | Professional role |
| audience | Text | Target audience |
| channel | Select | LinkedIn / X / Instagram |
| content_pillars | Text | 3 focus areas |
| system_prompt | Text | Writing brief + sample voice |
| avoid | Text | 10 hard rules (banned words, structures, phrases) |
| tone | Select | Tone descriptor |
| active | Checkbox | Pause/resume toggle |

### Sent Articles DB

Tracks every article sent so dedup works across days.

| Property | Type | Purpose |
|---|---|---|
| Title | Title | Article headline |
| Clean URL | Text | Normalised URL (lowercased, no query params) |
| Title Key | Text | Hash of article title for fuzzy matching |
| URL | URL | Original article link |
| Sent Date | Date | When the post was drafted |

## Voice DNA approach

The persona's `avoid` field contains 10 hard rules — short enough for Gemini Flash to follow. Full Voice DNA (4000+ words: banned vocabulary, structural rules, formatting, anti-overfitting guidance) lives in the Claude voice project, applied during final polish.

Hard rules enforced in n8n:
- No em dashes
- No "It's not X, it's Y" reframe constructions
- ~20 banned AI words (delve, leverage, seamless, transformative, etc.)
- No rule-of-three lists
- No rhetorical questions ending with three adjectives
- Contractions always
- Short paragraphs (1-2 sentences default)
- First person, direct address, active voice

Trying to enforce the full Voice DNA inside Gemini Flash failed. Flash glazes over long instruction sets. The split between n8n (rough structure) and voice project (final voice) handles this properly.

## Sample output

**Email subject:** `LI Draft [17 May] — Full-stack marketers replacing specialists`

**Email body (rough draft, pre-voice-project):**

> A prominent CMO is using AI to replace specialised marketing roles with 'full-stack' professionals. For founders, this means building lean marketing operations from day one. A single marketing lead, amplified by AI, can now handle content, analysis, and campaign management — work that once required a full department.
>
> What specific AI tools are expanding your marketing capabilities?

**After voice project polish (publish-ready):**

> A CMO at a public company just replaced 4 specialist marketing roles with 2 generalists who use AI.
>
> The economics are obvious. The pattern matters more. We're watching the marketing org compress, not because of AI hype, but because specialists optimise for craft and generalists optimise for outcomes. AI handles the craft.
>
> If you're a founder hiring your first marketer in 2026, looking for a generalist operator may give you the best outcome. Someone who can synthesize the org goals, translate it to marketing goals, create a strategy, and run all of it with tools.
>
> Are you still hiring specialists in 2026?

## What broke along the way

**Same post every day** in the original workflow. Root cause: no deduplication. Google News RSS ranks the same articles consistently, so the LLM kept picking from the same pool. Fixed by adding a Sent Articles DB and filtering against the last 7 days.

**Notion DB not found** in the n8n dropdown. Root cause: Notion integration didn't have access to the new DB. Fixed by adding the n8n connection to the DB via `... → Connections → Add n8n`.

**`Get Sent History` running 15 times.** Default behaviour: n8n runs nodes once per upstream item. Fixed by toggling **Execute Once** in Settings.

**Empty email body** despite clean JSON output. Root cause: `=` prefix mismatch on Gmail field expressions. n8n needs *either* the `=` prefix *or* expression mode toggled on, not both. Doubling it produces literal `=` in the output.

**Voice DNA being ignored by Gemini Flash.** Root cause: 4000-word ruleset is too long for Flash to follow. Fixed by splitting work: short ruleset in n8n + full Voice DNA in Claude voice project.

**Gemini 2.5 Pro quota too tight on free tier.** Tried upgrading the Write node to Pro for better instruction-following. Hit daily token limits within a few runs. Reverted to Flash + accepted that the n8n output is a rough draft, not a final post.

## Configuration

To run this workflow you'll need:

1. n8n instance (cloud or self-hosted)
2. Google Gemini API credential (Flash tier is enough)
3. Gmail OAuth2 credential
4. Notion OAuth2 credential
5. Personas DB and Sent Articles DB in Notion, with the n8n integration connected to both
6. DB IDs filled into the Notion nodes after import

## To activate

Toggle the workflow from Inactive → Active. It will run daily at 7 AM IST.

## Planned improvements

- Add a daily summary table to Notion: articles seen, articles sent, articles skipped (deduped)
- Move the Gemini Write step to Claude via Anthropic API for better Voice DNA adherence in-flow
- Add an LLM-judged quality score on each draft so the email subject signals "high signal" vs "low signal" drafts
- Consider a manual "topic queue" Notion DB that overrides RSS on days when there's a specific narrative I want to ride
- Explore direct LinkedIn publishing via API after a few weeks of validated draft quality
