# Pipeline Fix Round 2 — Content Quality, URLs, and Evergreen Posts

## Bug A — Generic filler template is firing instead of the real prompt

The "How to use ChatGPT" post used placeholder-style content:
```
Key feature 1: High performance and automation.
Key feature 2: Designed for rapid productivity.
```
This is not a bad AI response — it's a **hardcoded fallback/generic template** being used instead of routing to the correct category prompt (`ai_news.md` or a tutorial-style template). A "beginner's guide to ChatGPT" is news/explainer content, not a tool spotlight, and it got the AI Tools boilerplate treatment. Find and remove whatever generic template produces "Key feature 1/2" — it should never exist as a fallback; if categorization fails, the item should be rejected, not published with placeholder text.

**Ask Antigravity directly:** "Search the codebase for the literal string 'Key feature 1' or similar placeholder text — where does this template live, and why did this item get routed to it instead of a real category prompt?"

## Bug B — Empty-body post published (the original bug, resurfaced)

The PCMag/Gemini post was just a headline + "Read Full Article" — no body at all. The validation gate (min length ≥ 100 chars) should have caught this. Either:
- this row predates the fix and was manually approved from the old backlog, or
- there's a second code path (manual quick-add, dashboard shortcut, etc.) that writes directly to `APPROVED` without going through `validate_ai_response`.

**Ask Antigravity directly:** "Is there any way for a row to reach status=APPROVED without passing through validate_ai_response? Check the dashboard server and any manual-add functions specifically."

## Bug C — Google News redirect URLs instead of real source links

That giant `https://news.google.com/rss/articles/CBMi...` link is Google News's redirect wrapper, not the actual article URL. Fix at ingestion: when a source feed is Google News RSS, follow the redirect (HTTP GET with redirects allowed, or parse the decoded URL parameter) and store the **resolved canonical URL** in `source_url`, never the wrapper link. This also matters for your dedup logic — two different Google News wrapper links can point to the same article, so dedup keyed on the wrapper URL will miss real duplicates.

## Bug D — Length inconsistency ("big and small ratio")

Add explicit **min AND max** body length bounds in the validation gate, not just a minimum:
- News/explainer posts: ~600–1800 characters for body
- Tool/resource spotlights: ~400–1000 characters
- If a real story genuinely warrants more, that's fine per your original design (§18 "don't force big stories into 3-4 sentences") — but a post with *zero* body content should never pass, and this needs enforcing everywhere, not just the primary drafting path.

---

## New feature — Evergreen / Original Content Mode

You're asking for something the original design already scoped (Categories B, C, D, H in the design doc were never meant to depend on live news) but the current pipeline apparently treats everything as "fetch an article, then draft from it." Add a second content path:

**Topic Queue (new, separate from RSS ingestion):**
A rotating list of keywords/subtopics per evergreen category, e.g.:
```yaml
top10_prompts:
  - "AI prompts for students"
  - "AI prompts for debugging"
  - "AI prompts for research"
ai_career:
  - "ChatGPT tricks for students"
  - "Claude tricks for students"
  - "AI portfolio project ideas"
learning_resources:
  - "free resources to learn RAG"
  - "free resources to learn LangGraph"
```

For these, the AI drafts an **original post directly from its own knowledge**, using the matching prompt template from `prompts/`, no RSS fetch required. Guardrails still apply per category:
- `top10_prompts` / `ai_career`: fully original writing is fine, no external URL required.
- `learning_resources` / `ai_tools`: still must never invent a URL — if the AI can't verify a real resource URL for an item, it should omit that item rather than fabricate a link (this was already a rule in those prompt templates; just make sure the evergreen path uses them, not a separate ungated path).

A simple rotation (round-robin through the topic list, one per scheduled cron run per category) avoids repeating the same keyword every day and gives you a natural way to hit your 5-post/day target even on days when RSS turns up nothing draft-worthy.

---

## Corrective brief — paste to Antigravity

```
Two real bugs from live posts, plus one new feature:

1. Find and remove the generic "Key feature 1/2" placeholder template — no fallback
   template should ever be published. If category routing fails, reject the item,
   don't publish boilerplate.
2. Confirm whether any code path can set status=APPROVED without going through
   validate_ai_response (check dashboard_server.py and any manual-add function).
   Add the same validation gate to every path that can approve a row.
3. Fix Google News RSS ingestion to resolve and store the canonical article URL,
   not the news.google.com redirect wrapper — this also affects dedup accuracy.
4. Add a maximum body-length bound to the validation gate alongside the existing
   minimum, per category (see pipeline-fix-round-2.md for suggested ranges).
5. Build the Topic Queue / evergreen content path described in pipeline-fix-round-2.md
   for categories that don't need a live news source (Top 10 Prompts, AI Career,
   Learning Resources) — original AI-generated content using the existing prompt
   templates, with a rotating keyword list so we're not fully dependent on RSS
   turning up good stories every cycle.

Show me one example output from the new Topic Queue path and one from the fixed
Google News resolver before I approve moving forward.
```
