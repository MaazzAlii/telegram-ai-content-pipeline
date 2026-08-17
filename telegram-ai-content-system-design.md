# Telegram AI Content System — Technical Design (v1)

**Owner:** Maaz Ali (MaazzAlii)
**Scope:** Design only — no code yet. This is the blueprint for Version 1 (local n8n MVP) plus the roadmap for v2/v3/v4.

---

## 1. System Overview

A human-in-the-loop content pipeline:

```
RESEARCH → AI DRAFT → GOOGLE SHEETS QUEUE → HUMAN REVIEW → APPROVE → SCHEDULE → TELEGRAM PUBLISH
```

AI does research, drafting, scoring, and categorization. It never gets final publish authority — every row must reach `APPROVED` status, set by you, before the publisher workflow will touch it. Google Sheets is the single source of truth (the "editorial database") for v1; nothing about this design requires a database beyond that until v2.

The system is built almost entirely in **n8n**, with **Python only where n8n's native nodes are awkward** (e.g., dedupe scoring, HTML→Telegram-Markdown cleanup). No FastAPI service is needed for v1 — that's explicitly deferred to v2/v3 if a custom API genuinely becomes necessary (e.g., serving a dashboard, or hosting a local model behind an API).

---

## 2. Architecture Diagram (text form)

```
┌────────────────────────────────────────────────────────────────┐
│                         SOURCES LAYER                          │
│  RSS feeds │ Official blogs │ GitHub releases │ News APIs       │
└───────────────────────────┬──────────────────────────────────┘
                             │ (n8n Schedule Trigger, e.g. every 2h)
┌────────────────────────────▼──────────────────────────────────┐
│                    n8n: RESEARCH WORKFLOW                      │
│  Fetch → Parse → Normalize → Dedup check → Score → Categorize  │
└───────────────────────────┬──────────────────────────────────┘
                             │ candidates worth drafting
┌────────────────────────────▼──────────────────────────────────┐
│                 n8n: AI DRAFTING WORKFLOW                      │
│  AI Provider Router (Gemini/Mistral/Grok/OpenAI/Local)         │
│  → Generate hook/title/body/keypoints/hashtags/score           │
└───────────────────────────┬──────────────────────────────────┘
                             │ write row, status=REVIEW
┌────────────────────────────▼──────────────────────────────────┐
│                  GOOGLE SHEETS CONTENT QUEUE                   │
│  (editorial DB — see schema in §6)                              │
└───────────────────────────┬──────────────────────────────────┘
                             │ you edit / set status=APPROVED
┌────────────────────────────▼──────────────────────────────────┐
│                 n8n: SCHEDULING WORKFLOW                       │
│  Reads APPROVED rows → assigns/confirms Scheduled Date+Time    │
└───────────────────────────┬──────────────────────────────────┘
                             │ (n8n Schedule Trigger, e.g. every 5 min)
┌────────────────────────────▼──────────────────────────────────┐
│                 n8n: PUBLISHING WORKFLOW                       │
│  Check due & APPROVED & not published → Telegram Bot API       │
│  → write message_id, PUBLISHED, timestamp / or FAILED + error  │
└──────────────────────────────────────────────────────────────┘
```

Four separate n8n workflows, loosely coupled through the Sheet. This is deliberate: any one workflow can fail without breaking the others, and you can trigger/debug each independently.

---

## 3. Component List

| Component | Role | Required in v1? |
|---|---|---|
| n8n (local) | Orchestration, all four workflows | Yes |
| Google Sheets | Content queue / editorial DB | Yes |
| Telegram Bot API | Publishing + optional admin approval | Yes |
| AI Provider(s) | Drafting, scoring, categorization | Yes (at least one) |
| RSS/HTTP fetch nodes | Source ingestion | Yes |
| Python script(s) | Dedup similarity, text cleanup helpers | Optional, recommended |
| SQLite | Local cache (seen-URL hashes) | Optional |
| FastAPI | Custom backend | No — defer |
| PostgreSQL | Scaled DB | No — v2+ |
| Image generation | Visuals | No — v2+ |

---

## 4. Data Flow

1. **Research trigger** (n8n Schedule Trigger, e.g. every 2 hours) fans out to RSS/HTTP Request nodes per source.
2. Each item is normalized into a common shape: `{title, url, source, published_at, raw_summary}`.
3. **Dedup check**: hash the URL (and a normalized title) and check against a "seen" store (a Sheets tab or SQLite table). Drop exact repeats.
4. **Cheap pre-filter**: simple keyword/category match + recency check, done without calling an LLM at all (n8n `IF`/`Switch` nodes). This is the cost-control step from §32 of your spec.
5. Survivors go to the **AI Provider Router** for: category confirmation, importance score, and a decision of "draft-worthy y/n."
6. Draft-worthy items go to **AI drafting**: hook, title, body, key points, why-it-matters, hashtags, suggested time, confidence score.
7. A new row is appended to the Sheet with `status=REVIEW`.
8. You review in Sheets (or optionally via Telegram admin buttons, §11): edit inline, set `status=APPROVED` or `REJECTED`.
9. **Scheduling workflow** periodically scans `APPROVED` rows missing a firm `Scheduled Date/Time` and assigns the next open slot from the configured daily template (§13), respecting category-balance rules.
10. **Publishing workflow** runs frequently (e.g. every 5 min), looks for rows where `status=APPROVED`, `Scheduled Date/Time <= now`, and `Telegram Message ID` is empty. Publishes, then writes back `Telegram Message ID`, `status=PUBLISHED`, `Published At`. On failure, writes `status=FAILED` + `Error` and leaves it for retry/manual fix.

---

## 5. n8n Workflow Design

**Workflow A — Research & Ingest**
`Schedule Trigger → [RSS Read / HTTP Request per source] → Merge → Function (normalize) → Dedup Filter (Sheets/SQLite lookup) → Keyword Pre-filter → AI Router (classify/score) → IF draft-worthy → append to "Research Candidates" tab`

**Workflow B — AI Drafting**
`Schedule Trigger (or triggered from A) → Read "Research Candidates" where status=RESEARCHED → AI Router (draft generation, category-specific prompt template) → Format Telegram Markdown → Append/Update row in "Content Queue" tab, status=REVIEW`

**Workflow C — Scheduling**
`Schedule Trigger → Read Content Queue where status=APPROVED and Scheduled Date/Time empty → Apply slot template + diversity rule → Update row (Scheduled Date/Time, status stays APPROVED)`

**Workflow D — Publishing**
`Schedule Trigger (every 5 min) → Read Content Queue where status=APPROVED and due and not yet published → Telegram: sendMessage → On success: Update row (PUBLISHED, message id, timestamp) → On error: Update row (FAILED, error message) → (optional) Telegram admin alert on failure`

**Optional Workflow E — Telegram Admin Approval** (§11)
`Telegram Trigger (bot receives /review or scheduled digest) → send preview with inline buttons (Approve/Reject/Edit/Reschedule) → Webhook receives callback_query → Update corresponding Sheets row status`

Each workflow gets its own n8n credential set and its own error-handling branch (see §14).

---

## 6. Google Sheets Schema

**Tab: `Content Queue`** (matches your spec in full)

| Column | Notes |
|---|---|
| ID | UUID or incrementing string, e.g. `POST-000123` |
| Created At | ISO timestamp |
| Scheduled Date | `YYYY-MM-DD` |
| Scheduled Time | `HH:MM` (24h) |
| Category | one of the 10 categories (§5–14 of your spec) |
| Topic | short internal label |
| Headline | public-facing title |
| Draft Content | full formatted post body |
| Source | publication/site name |
| Source URL | primary link |
| Secondary Source | optional |
| Secondary URL | optional |
| Image Required | TRUE/FALSE |
| Image URL | optional, manual for v1 |
| Status | `RESEARCHED / DRAFT / REVIEW / APPROVED / REJECTED / SCHEDULED / PUBLISHED / FAILED` |
| Priority | Low/Med/High |
| AI Confidence | 0–100 |
| Human Notes | your editing notes |
| Published At | ISO timestamp, set by publisher |
| Telegram Message ID | set by publisher, used for dedupe-guard |
| Error | last error message, if any |

**Tab: `Research Candidates`** — pre-draft staging, same idea but lighter (title, url, source, category guess, score, seen_hash, status).

**Tab: `Seen URLs`** (or an SQLite table if you prefer local) — `url_hash, first_seen_at, title_normalized` — used purely for fast dedup lookups so you're not scanning the whole Content Queue every cycle.

**Tab: `Config`** — a small key/value sheet for schedule slot times, category ratio targets, and which AI provider is "primary" — so none of this is hard-coded in the workflow (per §25/§3 of your spec).

---

## 7. Telegram Bot Architecture

- One bot (via BotFather) with **publish** rights on your channel, added as admin.
- v1 only needs `sendMessage` (and optionally `sendPhoto` once images exist).
- Use `parse_mode: MarkdownV2` or `HTML` — decide once and stick to it, since Telegram's MarkdownV2 escaping is strict (n8n Function node to escape special characters is worth building early).
- Optional second bot (or same bot, private chat with you) for the admin-approval flow in §11, using `sendMessage` with `inline_keyboard` and a Telegram Trigger node listening for `callback_query`.
- Store the bot token only in n8n credentials, never in the Sheet or in workflow JSON.

---

## 8. AI Provider Architecture

Design this as a **router pattern**, not a hard dependency on one vendor:

```
AI ROUTER (n8n Function/Switch node or small Python function)
  input: {task_type, category, payload}
  → pick provider based on Config tab priority + last-known quota status
  → normalize output to one internal schema: {text, tokens_used, provider, confidence}
  providers: Gemini (primary candidate) → Mistral → Grok → OpenAI → Local model (fallback)
```

Practical implementation in n8n: a single "AI Router" sub-workflow that takes `{task, prompt, category}` and internally tries the primary provider's HTTP node; on error/quota response, falls through to the next provider in a `Try/Catch`-style branch (n8n's `Error Trigger` + `Continue On Fail` per node, chained). Each provider's specifics (auth header, endpoint, request shape) live only inside this one sub-workflow — every other workflow just calls it, so swapping providers later means editing one place.

Use **cheap/free models for cheap tasks** (dedup relevance check, category tagging) and reserve stronger models for actual drafting — this is the cost-control principle from §32.

---

## 9. Research / Source Architecture

- Start with **RSS** wherever possible (official blogs, arXiv categories, GitHub releases via `.atom` feeds) — free, no auth, low maintenance.
- Add a small curated source list per category rather than broad crawling — quality over volume, matching your §30 diversity goal.
- Source priority levels (§17 of your spec) get encoded as a `trust_level` field per source in the `Config` tab, and factored into the AI scoring prompt ("if trust_level=4, do not treat as confirmed fact; recommend verification against a Level 1–2 source").
- No scraping of sites that disallow it in `robots.txt` / ToS — stick to official feeds/APIs.

---

## 10. Content Generation Architecture

- One **prompt template per category** (10 templates), stored as text in n8n (or a `Prompts` tab) so they're easy to tune without touching workflow logic.
- Each template enforces: structure (per §19–21 of your spec), no fabricated stats, cite the source URL, keep tone professional/non-clickbait, and output a numeric confidence score.
- Output is requested in **strict JSON** from the model (see prompt-engineering note below) so n8n can map fields straight into Sheet columns without regex-parsing prose.

> Prompting tip for you to reuse: ask the model to respond with JSON only, no markdown fences, and give it the exact field names you want (`headline`, `body`, `key_points`, `hashtags`, `confidence`) — this removes almost all of the "fragile string parsing" pain in n8n.

---

## 11. Human Approval Architecture

- **Mandatory gate:** Workflow D (Publishing) filters strictly on `status=APPROVED`. No other status is ever eligible, full stop — this is enforced in the n8n `IF` node itself, not just as a convention.
- **v1 default:** review/approve directly in Google Sheets (edit `Status` and `Human Notes` cells).
- **Optional v1.5:** Telegram admin buttons (§11/§24 of your spec) — nice ergonomics, not required for the pipeline to work. Build it once Sheets-only review feels slow.

---

## 12. Scheduling Architecture

- `Config` tab holds a **slot template**, e.g.:

| Slot | Time | Category Weight |
|---|---|---|
| 1 | 09:00 | AI News |
| 2 | 12:00 | Prompts |
| 3 | 15:00 | Learning Resources |
| 4 | 18:00 | Tools/Automation |
| 5 | 21:00 | Industry/Career/Analysis |

- Workflow C assigns the next open slot to the oldest `APPROVED` item matching that slot's category, falling back to a "wildcard" slot if no matching-category item is ready — so the schedule never blocks on one empty category.
- Times/ratios are edited in the `Config` tab, never hard-coded in workflow JSON, so bumping to 7–10 posts/day later (§25) is a spreadsheet edit, not a rebuild.

---

## 13. Error Handling

Per failure mode from §33 of your spec:

| Failure | Handling |
|---|---|
| API quota exceeded | AI Router falls to next provider; log which provider was used per row |
| API timeout | n8n `Retry On Fail` (2–3 attempts, backoff), then fall through provider chain |
| Invalid AI response (bad JSON) | One retry with a "your last response wasn't valid JSON, return only JSON" repair prompt; if it fails again, mark `status=FAILED`, `Error` filled, skip |
| Telegram send failure | Retry x2; on persistent failure, `status=FAILED` + error, optional Telegram DM alert to you via the admin bot |
| Sheets API failure | n8n `Retry On Fail`; if Sheets is unreachable, workflow should stop cleanly rather than partially write |
| Duplicate article | Filtered at ingest via `Seen URLs`; never reaches drafting |
| Missing source / invalid URL | Reject at normalize step, don't draft |
| Empty AI response | Treated same as invalid JSON — retry once, then fail loud |

General rule: **every workflow ends with either a successful write or a `FAILED` write with a populated `Error` column** — nothing disappears silently, satisfying your "never silently fail" requirement.

---

## 14. Security

- All secrets (Telegram bot token, AI API keys, Google service account) live in **n8n Credentials**, referenced by name in nodes — never pasted into node parameters as literal text, never written to any Sheet cell.
- Google Sheets access via a **service account** with access scoped only to the specific spreadsheet (not full Drive access).
- If/when you self-host on a VPS, put n8n behind basic auth or a reverse proxy with auth (n8n supports this natively), and keep the VPS firewall closed except for the ports n8n/Telegram webhooks need.
- `.env`/credential files excluded from any git repo (`.gitignore`) if you version-control the workflow JSON exports.

---

## 15. Local Development Architecture

**Requirements:**
- n8n (already installed) running locally, e.g. `http://localhost:5678`
- Node.js (n8n's runtime — already satisfied if n8n runs)
- Python 3.x (for optional helper scripts) with a venv
- Google Cloud service account with Sheets API enabled, JSON key file
- Telegram bot created via BotFather, token saved
- A private Telegram channel (or your real one, muted, for testing) to publish test posts

**Suggested folder structure** (for the parts that live outside n8n's own storage — workflow JSON exports, prompt templates, helper scripts):

```
telegram-ai-content-system/
├── workflows/                # exported n8n workflow JSON (version-controlled)
│   ├── A-research.json
│   ├── B-drafting.json
│   ├── C-scheduling.json
│   └── D-publishing.json
├── prompts/                  # one .txt/.md per category prompt template
│   ├── ai_news.md
│   ├── top10_prompts.md
│   └── ...
├── scripts/                  # optional Python helpers (dedup similarity, cleanup)
│   ├── dedup.py
│   └── requirements.txt
├── config/
│   └── sources.yaml           # curated RSS/source list per category, with trust_level
├── .env.example                # documents required env var names, no real secrets
└── README.md
```

- **Testing:** run each workflow manually in n8n's editor (pin test data) before enabling the schedule trigger; use a private test Telegram channel first.
- **Debugging:** n8n's execution log + "pin data" feature to replay a failed run without re-hitting APIs/quota.

---

## 16. Production / VPS Architecture

**Key limitation to state plainly (per §36 of your spec): your laptop being off or asleep means nothing publishes.** Version 1 is for building/testing the pipeline, not for 24/7 operation.

Migration path when ready:
1. Provision a small VPS (1 vCPU / 1–2GB RAM is plenty for n8n + light traffic — e.g. a $4–6/mo box).
2. Install n8n (Docker is the cleanest route) with a persistent volume for its SQLite/Postgres data.
3. Export workflows from local n8n, import into VPS n8n; re-enter credentials there (they don't migrate with the JSON export by default).
4. Point the same Google Sheet and Telegram bot at the VPS instance — no changes needed on those ends.
5. Put n8n behind a reverse proxy (Caddy/Nginx) with HTTPS and basic auth.
6. Turn on the schedule triggers on the VPS; turn them off locally to avoid double-publishing.

---

## 17. Folder Structure

See §15 above — same structure serves both local and VPS; only the n8n instance and credentials differ.

---

## 18. Required APIs

- Telegram Bot API (free)
- Google Sheets API (free, via service account)
- At least one LLM API (see §19 cost table)
- RSS feeds (free, no API key)

---

## 19. Required Credentials

- Telegram bot token
- Google service account JSON (Sheets scope)
- One or more LLM API keys (Gemini / Mistral / Grok / OpenAI — whichever you enable)
- (Optional) SQLite file path, no credential needed

---

## 20–21. Estimated Cost & Free/Low-Cost Alternatives

I don't have current, verified pricing/quota numbers for Gemini, Mistral, Grok, and OpenAI's free tiers in front of me, and these change often enough that I'd rather check live figures than guess — happy to pull current free-tier limits for each provider if you want them before you pick a primary. What's safe to say architecturally: n8n (self-hosted), Google Sheets, RSS, and the Telegram Bot API are all free regardless of provider pricing, so your only recurring cost in v1 is whatever LLM calls you make — and the cost-control design in §9/§13 (cheap pre-filtering before any LLM call, category-cheap-task routing) is what keeps that number low no matter which provider you land on.

---

## 22. Version 1 Implementation Plan (build order)

1. Google Sheet: create `Content Queue`, `Research Candidates`, `Seen URLs`, `Config` tabs with the schemas above.
2. Telegram bot: create via BotFather, add as channel admin, test a manual `sendMessage` call from n8n.
3. Workflow D (Publishing) first, oddly enough — build it against a manually-filled test row so you can prove Sheets→Telegram works end to end before anything upstream exists.
4. Workflow A (Research) for **one category only** (e.g. AI News, since you have the clearest source list) — get normalize + dedup + basic scoring working.
5. Workflow B (Drafting) for that same one category — nail the JSON-output prompt pattern.
6. Manually approve a few rows in Sheets, confirm Workflow D actually publishes them.
7. Add Workflow C (Scheduling) once you're comfortable approving faster than the schedule needs.
8. Expand Workflow A/B to the remaining categories one at a time, reusing the pattern.
9. Add the AI Router's fallback provider once you've hit a quota limit for real (don't build the fallback logic speculatively before you've felt the pain).

---

## 23. Version 2 Roadmap

- More sources per category; better dedup (embedding-similarity, not just URL hash)
- Secondary-source verification step before "breaking news" posts
- Telegram admin approval workflow (§11) if Sheets review starts feeling slow
- Basic analytics (which categories/times get more engagement) feeding back into the `Config` slot weights
- Move `Seen URLs`/logs from Sheets to SQLite if the sheet gets slow

---

## 24. Version 3 Roadmap

Only after v1/v2 are stable and boring: the multi-agent pipeline (Research → Verification → Strategy → Writer → Quality → Human → Publisher) from your §37. This is a genuine agentic system and worth its own design pass when you get there — not something to sketch prematurely now.

---

## 25. Testing Strategy

- Unit-level: pin sample data in each n8n node during build, don't hit real APIs while iterating on logic.
- Integration: run each workflow manually end-to-end against a **private test Telegram channel** before pointing at the real channel.
- Load a week of realistic source data once and dry-run the full pipeline (research→draft→review) without publishing, to sanity-check volume and category balance.
- Only enable the real schedule triggers on the actual channel after a few clean dry runs.

---

## 26. Deployment Strategy

Local-first (§15) until the pipeline is proven and you're personally approving/publishing comfortably for at least a couple of weeks — then migrate to VPS (§16) for 24/7 operation. Don't deploy to a VPS before the workflow logic is settled; you'll just be debugging in two places at once.

---

## What Goes Where

**Built entirely inside n8n:**
- All four core workflows (research trigger/fetch, AI calls via HTTP nodes, Sheets read/write, Telegram publish)
- Retry/error branching
- Scheduling logic (IF/Switch nodes against the Config tab)

**Requires Python (optional helper scripts, not a service):**
- Similarity-based dedup (if URL-hash dedup proves too weak) — e.g. simple TF-IDF or embedding cosine similarity
- Any text cleanup/Markdown-escaping logic that's awkward as an n8n Function node

**Requires an external API:**
- Telegram Bot API, Google Sheets API, chosen LLM API(s), RSS feeds (no key needed)

**Should remain manual (v1):**
- Final approve/reject decision
- Image creation (if used at all)
- Source list curation (don't auto-discover new sources yet)

**Should NOT be built yet:**
- FastAPI backend
- PostgreSQL
- Multi-agent architecture (v3)
- Multi-platform publishing (v4)
- Automatic image generation
- Telegram admin-approval workflow (nice-to-have, not v1-critical)

---

## Critical Rule, Restated

Build Workflow D → A → B → manual approve loop → C, in that order, one category at a time. Resist adding the AI provider fallback chain, the admin-approval bot, or dedup embeddings until the simple version has actually hit the wall that feature solves. Everything above is designed so each of those upgrades is additive, not a rewrite.
