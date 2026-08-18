"""
Daily DM Digest Engine for Telegram AI Content Pipeline.

Generates and sends an executive daily performance summary to the admin via Telegram DM:
- Total posts published today and breakdown by target (BOTH / CHANNEL_1 / CHANNEL_2).
- Health and failure/rejection summary with specific error reasons.
- Live subscriber counts for each channel via getChatMemberCount with daily delta tracking.
- State persisted locally in config/subscriber_state.json.

Usage:
    python scripts/daily_digest.py
    python scripts/daily_digest.py --dry-run
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
STATE_FILE = CONFIG_DIR / "subscriber_state.json"
CREDENTIALS_FILE = "telegram-ai-pipeline-85177bbe5835.json"
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")

# Import publishing utilities
sys.path.insert(0, str(BASE_DIR / "scripts"))
from publish_telegram import load_env_var, call_telegram_api, send_telegram_message


def get_channel_subscriber_count(bot_token: str, channel_id: str, timeout: int = 6) -> int:
    """Fetches total subscriber count for a Telegram channel using getChatMemberCount."""
    if not bot_token or not channel_id:
        return None
    
    res = call_telegram_api(bot_token, "getChatMemberCount", {"chat_id": channel_id}, timeout=timeout)
    if res.get("ok"):
        return res.get("result", 0)
    
    return None


def load_subscriber_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_subscriber_state(state: dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Could not save subscriber state: {e}")


def fetch_daily_metrics(credentials_path: str, spreadsheet_id: str) -> dict:
    """Reads Content_Queue and Published_Archive from Google Sheets to compute today's stats."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = BASE_DIR / credentials_path
    if not creds_path.exists():
        print(f"[!] Credentials file not found at: {creds_path}")
        return {}

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    # 1. Fetch Content_Queue rows
    res_queue = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A2:N"
    ).execute()
    queue_rows = res_queue.get("values", [])

    published_today = []
    both_count = 0
    ch1_only_count = 0
    ch2_only_count = 0
    failures_today = []

    for r in queue_rows:
        status = r[7].strip() if len(r) > 7 and r[7] else ""
        published_at = r[11].strip() if len(r) > 11 and r[11] else ""
        error_log = r[12].strip() if len(r) > 12 and r[12] else ""
        post_target = (r[13].strip() if len(r) > 13 and r[13] else "BOTH").upper()
        title = r[1].strip() if len(r) > 1 and r[1] else "Untitled"

        if status == "PUBLISHED" and (published_at.startswith(today_str) or not published_at):
            published_today.append({"title": title, "target": post_target})
            if post_target == "CHANNEL_1":
                ch1_only_count += 1
            elif post_target == "CHANNEL_2":
                ch2_only_count += 1
            else:
                both_count += 1
        elif status.startswith("REJECTED") or status == "FAILED":
            reason = error_log or status
            failures_today.append({"title": title, "reason": reason})

    return {
        "date": today_str,
        "total_published": len(published_today),
        "target_breakdown": {
            "BOTH": both_count,
            "CHANNEL_1": ch1_only_count,
            "CHANNEL_2": ch2_only_count
        },
        "failures": failures_today
    }


def generate_daily_digest(credentials_path: str, spreadsheet_id: str, bot_token: str, ch1_id: str, ch2_id: str) -> tuple:
    """Builds the formatted markdown digest text and tracks subscriber delta."""
    metrics = fetch_daily_metrics(credentials_path, spreadsheet_id)
    today_str = metrics.get("date", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))

    # Track subscriber counts
    state = load_subscriber_state()
    history = state.get("channels", {})
    new_history = {}

    ch1_count = get_channel_subscriber_count(bot_token, ch1_id) if ch1_id else None
    ch2_count = get_channel_subscriber_count(bot_token, ch2_id) if ch2_id else None

    # Compute deltas
    def format_delta(current, channel_key):
        if current is None:
            return "N/A"
        prev_data = history.get(channel_key, {})
        prev_count = prev_data.get("count")
        prev_date = prev_data.get("date", "")
        
        delta_str = ""
        if prev_count is not None and prev_date != today_str:
            diff = current - prev_count
            if diff > 0:
                delta_str = f" (+{diff} vs yesterday)"
            elif diff < 0:
                delta_str = f" ({diff} vs yesterday)"
            else:
                delta_str = " (±0 vs yesterday)"
        elif prev_count is None:
            delta_str = " (initial count)"
        else:
            delta_str = " (tracked today)"

        new_history[channel_key] = {"count": current, "date": today_str}
        return f"`{current}` members{delta_str}"

    ch1_delta_text = format_delta(ch1_count, ch1_id or "channel_1")
    ch2_delta_text = format_delta(ch2_count, ch2_id or "channel_2") if ch2_id else None

    # Save state
    save_subscriber_state({"last_updated": today_str, "channels": new_history})

    # Failure summary
    failures = metrics.get("failures", [])
    failure_text = ""
    if not failures:
        failure_text = "• ✅ 0 failures / All posts validated cleanly"
    else:
        # Group by reason
        reason_counts = {}
        for f in failures:
            r_str = f.get("reason", "Unknown validation error")
            reason_counts[r_str] = reason_counts.get(r_str, 0) + 1
        
        f_lines = [f"• ❌ `{r}` ({cnt}x)" for r, cnt in reason_counts.items()]
        failure_text = "\n".join(f_lines)

    ch1_paused = load_env_var("CHANNEL_1_PAUSED", "false").lower() in ("true", "1", "yes")
    ch2_paused = load_env_var("CHANNEL_2_PAUSED", "false").lower() in ("true", "1", "yes")

    target_breakdown = metrics.get("target_breakdown", {})
    total_pub = metrics.get("total_published", 0)

    # Compose rich markdown digest
    msg = (
        f"📊 *Telegram AI Pipeline — Daily Executive Digest*\n"
        f"📅 *Date:* `{today_str}`\n\n"
        f"🚀 *Published Content Today:* *{total_pub}* post(s)\n"
        f"• 🌐 *BOTH Channels:* {target_breakdown.get('BOTH', 0)}\n"
        f"• 📢 *Channel 1 Only:* {target_breakdown.get('CHANNEL_1', 0)}\n"
        f"• 📣 *Channel 2 Only:* {target_breakdown.get('CHANNEL_2', 0)}\n\n"
        f"👥 *Subscriber Audience & Growth:*\n"
        f"• 📢 *Channel 1 ({ch1_id or 'Primary'}):* {ch1_delta_text}\n"
    )

    if ch2_id:
        msg += f"• 📣 *Channel 2 ({ch2_id}):* {ch2_delta_text}\n"

    msg += (
        f"\n⚙️ *Channel Status:*\n"
        f"• Channel 1: {'⏸️ PAUSED' if ch1_paused else '🟢 ACTIVE'}\n"
    )
    if ch2_id:
        msg += f"• Channel 2: {'⏸️ PAUSED' if ch2_paused else '🟢 ACTIVE'}\n"

    msg += (
        f"\n🛡️ *Validation Gate & Errors ({len(failures)} item(s)):*\n"
        f"{failure_text}\n\n"
        f"💡 _Pipeline Auto-Pilot is operating normally._"
    )

    return msg, metrics


def send_daily_digest(credentials_path: str = CREDENTIALS_FILE, spreadsheet_id: str = SPREADSHEET_ID, dry_run: bool = False) -> dict:
    """Generates the daily digest and delivers it to the user's private Telegram chat."""
    bot_token = load_env_var("TELEGRAM_BOT_TOKEN")
    ch1_id = load_env_var("TELEGRAM_CHANNEL_1_ID") or load_env_var("TELEGRAM_CHANNEL_ID")
    ch2_id = load_env_var("TELEGRAM_CHANNEL_2_ID")
    admin_chat_id = load_env_var("TELEGRAM_ADMIN_CHAT_ID")

    print("\n" + "=" * 60)
    print("📊 Generating Telegram Daily Executive DM Digest...")
    print("=" * 60)

    digest_text, metrics = generate_daily_digest(credentials_path, spreadsheet_id, bot_token, ch1_id, ch2_id)

    print("\n--- [DIGEST PREVIEW] ---")
    print(digest_text)
    print("------------------------\n")

    if dry_run:
        print("[OK] Dry run completed. Message not dispatched.")
        return {"ok": True, "dry_run": True, "text": digest_text}

    if not admin_chat_id:
        print("[!] Warning: TELEGRAM_ADMIN_CHAT_ID is not configured in .env.")
        print("💡 To receive daily DM digests, add your Telegram User ID to .env (e.g. TELEGRAM_ADMIN_CHAT_ID=123456789).")
        return {"ok": False, "error": "TELEGRAM_ADMIN_CHAT_ID not set in .env", "text": digest_text}

    if not bot_token:
        print("[!] Error: TELEGRAM_BOT_TOKEN is not set.")
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not set"}

    print(f"[+] Sending Daily DM Digest to Admin User (Chat ID: {admin_chat_id})...")
    res = send_telegram_message(bot_token, admin_chat_id, digest_text)

    if res.get("ok"):
        print("[SUCCESS] 🚀 Daily DM Digest delivered successfully to Admin!")
        return {"ok": True, "message_id": res.get("result", {}).get("message_id")}
    else:
        err = res.get("description", "Unknown error sending DM")
        print(f"[!] Failed to deliver Daily DM Digest: {err}")
        print("💡 Ensure you have started a private conversation with the bot (/start in Telegram).")
        return {"ok": False, "error": err}


def main():
    parser = argparse.ArgumentParser(description="Send Daily DM Digest to Admin via Telegram")
    parser.add_argument("--credentials", "-c", default=CREDENTIALS_FILE)
    parser.add_argument("--sheet-id", "-s", default=SPREADSHEET_ID)
    parser.add_argument("--dry-run", action="store_true", help="Print digest to console without sending DM")

    args = parser.parse_args()
    send_daily_digest(args.credentials, args.sheet_id, args.dry_run)


if __name__ == "__main__":
    main()
