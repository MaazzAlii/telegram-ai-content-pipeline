# Pipeline Fix & Deployment Spec — v1.1

Root cause of everything wrong in the live channel dump: **there is no validation gate between "AI drafted something" and "it gets a Sheets row / gets published."** Every fix below closes one specific hole. Build all of them before re-enabling the Publishing trigger.

---

## FIX 1 — Validation Gate (insert into Workflow B, before writing to Content Queue)

After the AI Router returns a drafting response, run it through these checks **in order**, entirely with n8n `IF`/`Function` nodes — no extra LLM call needed for most of this, so it costs nothing extra:

```
1. JSON PARSE CHECK
   Try JSON.parse(llm_response).
   FAIL → do not write a Content Queue row. Write to a "Drafting_Errors" log
          (or just the Error column on the Research Candidates row) and stop.
          Do NOT retry more than once total.

2. REQUIRED FIELDS CHECK
   Required: headline, body, source_url (or url, for non-news categories), category.
   Any missing/empty → reject, same as above.

3. MINIMUM LENGTH CHECK
   body.length < 100 characters → reject. This alone would have caught every
   truncated-JSON-leak post in your dump, since a real body is always longer.

4. REFUSAL / OUT-OF-SCOPE PHRASE CHECK
   If body OR headline contains any of (case-insensitive):
     "does not contain information", "not relevant to", "out of scope",
     "i cannot", "i'm unable to", "no information provided", "topic out of scope"
   → reject. This is a static string match, not another AI call — cheap and reliable.

5. DUPLICATE HASHTAG / FORMAT SANITY CHECK
   - hashtags must use single "#", strip any "##" down to "#"
   - body must not contain "Key takeaways" (or equivalent section header) twice
   - if either check fails, don't reject the whole post — auto-clean it
     (regex replace) rather than discarding good content over a formatting slip

ONLY rows that pass 1–4 (with 5 auto-cleaned) get written to Content Queue,
and they get status=REVIEW — never anything further downstream automatically.
```

This is the single most important fix. Everything else matters, but this is what stops garbage from ever reaching a human or Telegram again.

---

## FIX 2 — Dedup, enforced at two separate points (not one)

Your dump shows the *same* story published 6 times — that means dedup failed at both places it should have caught it:

**Point A — Research workflow (before drafting):**
Before appending anything to `Research Candidates`, hash the URL and check it against the `Seen URLs` tab. If it exists, skip. Immediately after checking, write the hash to `Seen URLs` — not after drafting, not after publishing. Reserve the URL the moment you've decided to consider it, so two runs of Workflow A 2 hours apart can't both grab the same story.

**Point B — Publishing workflow (before sending to Telegram):**
Add a hard `IF` condition: `Telegram Message ID` column must be empty AND `status = APPROVED`. If either is false, skip the row — no exceptions. This is what should have stopped the 6x repeat even if dedup at Point A somehow failed. Right now this check is either missing or the Scheduling workflow is re-assigning the same row a new slot each run without checking if it already has a message ID.

Also check: is Workflow C (Scheduling) possibly re-processing already-`PUBLISHED` rows because its filter is `status=APPROVED` and something is resetting status back to `APPROVED` after publish? Verify Workflow D actually writes `status=PUBLISHED` successfully — if that write is silently failing, the row stays `APPROVED` forever and every publish cycle picks it up again. This matches your symptom exactly (identical post, back to back) — check this specifically.

---

## FIX 3 — Source Curation (this is why trebuchets and DuckDB showed up)

Your Research workflow is pulling from sources broader than your 10 categories. Fix `config/sources.yaml` to **only** include feeds that are inherently on-topic (official AI company blogs, arXiv AI categories, specific dev-tool release feeds, cybersecurity advisories) rather than general tech-news aggregators (Hacker News firehose, general "interesting links" feeds) that will always contain off-topic curiosities like trebuchets.

If you want to keep a broader source for volume, add a **category pre-filter** before drafting even starts: a cheap keyword/topic check (no LLM call) that requires the title/summary to match at least one of your 10 categories' keyword sets before it's allowed into `Research Candidates` at all. This is cheaper and more reliable than trusting the drafting prompt to self-censor off-topic input — by the time it reaches drafting, you've already spent the API call.

---

## FIX 4 — Formatting Consistency

- Enforce single `#hashtag` format at generation time (already covered by all 10 prompt templates I gave you — the leak you're seeing suggests Antigravity may have written its own formatting logic instead of using those templates verbatim). Worth checking: did it actually wire up `prompts/*.md` as the system prompts, or did it generate its own drafting prompts inline in the workflow? Ask it directly.
- One "Key takeaways" section per post — if you're seeing it twice, something is concatenating two AI responses into one post (possibly a retry that appended instead of replaced).

---

## Corrective Brief — paste this to Antigravity

```
STOP. The live channel has published broken content — raw JSON leaks, 6x duplicate
posts, and off-topic content (trebuchet, DuckDB, wildfire articles) that has nothing
to do with our 10 categories.

Immediate action:
1. Deactivate the Publishing workflow's schedule trigger right now so nothing more
   goes out while we fix this.
2. Show me exactly how Workflow B currently handles the AI Router's response —
   specifically, is there ANY validation before writing to Content Queue, and is
   it using the system prompts from prompts/*.md verbatim, or did you write your
   own prompt/parsing logic? I need the real answer, not a summary.
3. Show me the exact filter condition on Workflow D's Sheets read step — I suspect
   it is not excluding rows that already have a Telegram Message ID, which would
   explain the Apple ATT story posting 6 times.

Do not re-enable publishing until all of these are built and I've tested them
against a private test channel:

1. Validation gate in Workflow B per pipeline-fix-and-deployment-spec.md FIX 1 —
   JSON parse check, required-field check, minimum length check, refusal/out-of-
   scope phrase check, before any row reaches Content Queue.
2. Dedup enforced at BOTH: (a) Research workflow before appending to Research
   Candidates, writing to Seen URLs immediately on decision, and (b) Publishing
   workflow with a hard filter requiring Telegram Message ID to be empty.
3. Confirm Workflow D is actually writing status=PUBLISHED successfully after
   each send — if that write were failing, rows would stay APPROVED and get
   re-picked every cycle, which matches what happened.
4. Tighten config/sources.yaml to only AI/dev/cybersecurity-relevant feeds, or
   add a cheap keyword pre-filter before any item reaches drafting.
5. Confirm prompts/*.md are wired in as the actual system prompts for Workflow B,
   not reimplemented — this is required, not optional.

After each fix, show me a before/after example from the actual data, not just a
description of the change. Wait for my confirmation before re-enabling the live
publish trigger.
```

---

## Deployment (Render, or the VPS route from the original design)

You mentioned Render — a few things worth knowing before you pick it:

**Render works, with one catch:** n8n runs fine on Render as a Docker service (Render supports deploying arbitrary Docker images), and you'd attach a persistent disk for `/home/node/.n8n` the same way as the local Docker volume. But **Render's free tier spins the service down after inactivity** — for a system that needs Schedule Triggers firing every few minutes 24/7, that defeats the purpose (same "laptop asleep" problem the original design flagged in §36, just relocated to a cloud dyno). You'd need Render's paid "Starter" instance tier (not the free tier) to get an always-on service — roughly $7/mo territory as of when I last checked, though pricing changes, so verify current numbers on Render's site before committing.

**Alternative — small VPS (Hetzner/DigitalOcean, ~$4–6/mo), per the original design's §16:** slightly more setup (you manage the Docker Compose + reverse proxy yourself) but no idle-spindown risk and full control. This is what the original design doc recommended and it still holds.

Either way, the deployment steps are the same shape:
1. Push your repo (with `docker-compose.yml`, `workflows/`, `prompts/`, `config/`) to GitHub — already in place.
2. On the server (Render service or VPS), pull the repo, run `docker compose up -d`.
3. Re-enter all credentials fresh inside that instance's n8n UI — they do not travel with the git repo (correctly, since they're gitignored).
4. Re-import the workflow JSON files from `workflows/`.
5. Point the same Google Sheet and Telegram bot at this instance; deactivate any local n8n schedule triggers so you don't double-publish from two running instances at once.

**Don't deploy until Fix 1–5 above are verified working against a private test channel.** Moving a broken pipeline to a server just means it breaks your real channel faster and with less oversight while you're not watching it run locally.
