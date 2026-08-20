# Feature Brief — Dual-Channel Telegram Posting

## Ground rule

Add the following as **pure additions**. Do not modify, refactor, or touch the
existing validation gate (`validate_ai_response`), dedup logic (Point A / Point B),
or drafting/prompt-routing logic in `process_ai_content.py`. If any item below
seems to require changing that existing logic, stop and ask first instead of
proceeding.

## Architecture

**One bot, two channels.** Do not create a second bot token. The existing
`TELEGRAM_BOT_TOKEN` is added as admin (with Post Messages permission) to both
channels and handles both.

```
                ┌───► Channel 1
[ Single Bot ] ─┤
                └───► Channel 2
```

`.env` / GitHub Secrets:
```env
TELEGRAM_BOT_TOKEN=<existing token, unchanged>
TELEGRAM_CHANNEL_1_ID=@channel_one
TELEGRAM_CHANNEL_2_ID=@channel_two
TELEGRAM_ADMIN_CHAT_ID=<my personal numeric Telegram ID, for the digest DM>
```

## 1. Per-post channel targeting

- Add a **`Post Target`** column to `Content Queue`: values `BOTH` / `CHANNEL_1` / `CHANNEL_2`.
- Default to `BOTH` for every newly drafted row (both RSS-sourced and evergreen paths).
- Add a dropdown for this in the dashboard's edit/approve modal, next to Approve.
- `publish_telegram.py` reads `Post Target` per row and sends only to the selected
  channel(s). The non-selected channel's message-ID column is left empty and is
  never touched for that row.
- Add a **10–30 second delay** between sending to Channel 1 and Channel 2 for the
  same row (avoids identical-timestamp posts on both channels).

## 2. Sheet schema

Add two separate columns, not one:
- `Telegram Message ID (Channel 1)`
- `Telegram Message ID (Channel 2)`

Point-B dedup (publish-time duplicate check) must check each column independently —
only skip sending to a channel if *that channel's* ID column is already filled.

## 3. Row status logic

- `status = PUBLISHED` means "sent successfully to at least one selected channel."
- Add a separate per-channel result field (success / failed + reason) so partial
  failures are visible in the Sheet, not silently swallowed.

## 4. Bot permission health-check

Before publishing each cron cycle, call `getChatMember` for the bot against both
channel IDs. If it lacks admin/post rights on either, log a clear top-level warning
(not buried inside a per-row error) and skip sending to that channel for the whole
cycle rather than failing row-by-row.

## 5. Per-channel pause flag

Add `CHANNEL_1_PAUSED` / `CHANNEL_2_PAUSED` to the `Config` tab (or `.env`, whichever
matches how Config is currently read). If a channel is paused, skip it entirely for
every row, regardless of that row's `Post Target` value. This lets me pause one whole
channel without editing every row.

## 6. Daily digest DM

- Sent once per day (last run of the day, or a separate scheduled job) as a private
  Telegram message to `TELEGRAM_ADMIN_CHAT_ID`, via the same bot.
- Include: total posts published today, breakdown by target (`BOTH` / `CHANNEL_1`-only
  / `CHANNEL_2`-only), failure count with reasons, and current subscriber count per
  channel (`getChatMemberCount`) plus the change vs. yesterday's count (store
  yesterday's count somewhere simple — a small state file, or a row in `Config` —
  to compute the delta).
- Do **not** attempt to show per-post view counts or reactions — these require a
  logged-in user account (Telethon/Pyrogram) or a persistent listener process, neither
  of which exists in this architecture. If there's a way to get them without adding
  a new dependency or account, explain the tradeoffs before building anything —
  don't build it silently.

## Testing requirement

Test every item above — target selection (`BOTH`, `CHANNEL_1`, `CHANNEL_2`), the
delay, the health-check, the pause flags, and the digest DM — against **two private
test channels**, not the real channels, before this touches live traffic.
