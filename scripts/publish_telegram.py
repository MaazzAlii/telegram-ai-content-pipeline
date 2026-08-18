"""
Telegram Publisher for Telegram AI Content Pipeline.

Features:
- Reads APPROVED items from Content_Queue in Google Sheets.
- Pre-publish bot permission health-check (getChatMember verification on both channels).
- Per-post channel targeting (BOTH / CHANNEL_1 / CHANNEL_2).
- Per-channel pause flags (CHANNEL_1_PAUSED / CHANNEL_2_PAUSED).
- 10-30 second broadcast delay between Channel 1 and Channel 2 for the same post.
- Preserves Point B deduplication and validation gate.

Usage:
    python scripts/publish_telegram.py --sheet-id 1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE
"""

import os
import sys
import re
import json
import time
import random
import argparse
import datetime
import urllib.request
import urllib.parse
from pathlib import Path

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_var(key: str, default: str = "") -> str:
    if key in os.environ:
        return os.environ[key]
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def get_telegram_opener():
    proxy = load_env_var("HTTPS_PROXY") or load_env_var("HTTP_PROXY")
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    return urllib.request.build_opener(*handlers)


def call_telegram_api(bot_token: str, method: str, payload: dict = None, timeout: int = 15) -> dict:
    """Generic helper to call Telegram Bot API methods with proxy and timeout support."""
    base_url = load_env_var("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    url = f"{base_url.rstrip('/')}/bot{bot_token}/{method}"
    opener = get_telegram_opener()

    try:
        if payload is not None:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
        else:
            req = urllib.request.Request(url)

        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return json.loads(err_body)
        except Exception:
            return {"ok": False, "description": err_body}
    except (TimeoutError, urllib.error.URLError) as e:
        return {"ok": False, "description": f"Connection/SSL Timeout to Telegram API: {e}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def check_bot_permissions(bot_token: str, channel_1_id: str, channel_2_id: str = "", timeout: int = 8) -> dict:
    """
    Health-check verifying bot membership and administrator/posting privileges on both channels.
    Logs a clear top-level warning if permissions are missing.
    """
    if not bot_token:
        print("\n**********************************************************************")
        print("⚠️ [HEALTH CHECK WARNING] TELEGRAM_BOT_TOKEN is not configured in .env!")
        print("**********************************************************************\n")
        return {"ok": False, "error": "Bot token missing"}

    # 1. Get Bot info
    me_res = call_telegram_api(bot_token, "getMe", timeout=timeout)
    if not me_res.get("ok"):
        err = me_res.get("description", "Failed to contact Telegram API")
        print("\n**********************************************************************")
        print(f"⚠️ [HEALTH CHECK WARNING] Could not connect to Telegram Bot API (getMe failed): {err}")
        print("💡 Check your internet connection or proxy/VPN settings.")
        print("**********************************************************************\n")
        return {"ok": False, "error": err}

    bot_info = me_res.get("result", {})
    bot_id = bot_info.get("id")
    bot_username = bot_info.get("username", "UnknownBot")
    print(f"[HEALTH CHECK] 🤖 Bot authenticated: @{bot_username} (ID: {bot_id})")

    channels_to_check = []
    if channel_1_id:
        channels_to_check.append(("Channel 1", channel_1_id))
    if channel_2_id:
        channels_to_check.append(("Channel 2", channel_2_id))

    health_status = {"ok": True, "bot_username": bot_username, "bot_id": bot_id, "channels": {}}

    for ch_name, ch_id in channels_to_check:
        member_res = call_telegram_api(bot_token, "getChatMember", {"chat_id": ch_id, "user_id": bot_id}, timeout=timeout)
        if member_res.get("ok"):
            res_data = member_res.get("result", {})
            status = res_data.get("status", "")
            can_post = res_data.get("can_post_messages", True if status == "creator" else False)
            
            if status in ["administrator", "creator"]:
                print(f"  [OK] ✅ {ch_name} ({ch_id}): Bot is {status.upper()} (can_post_messages: {can_post})")
                health_status["channels"][ch_name] = {"ok": True, "status": status, "can_post": can_post}
            else:
                print("\n**********************************************************************")
                print(f"⚠️ [HEALTH CHECK WARNING] Bot @{bot_username} lacks admin rights on {ch_name} ({ch_id})!")
                print(f"   Current Member Status: '{status}'. Bot must be an Administrator with Post permissions.")
                print("**********************************************************************\n")
                health_status["ok"] = False
                health_status["channels"][ch_name] = {"ok": False, "status": status, "can_post": False}
        else:
            err = member_res.get("description", "Unknown error")
            print("\n**********************************************************************")
            print(f"⚠️ [HEALTH CHECK WARNING] Could not verify bot rights on {ch_name} ({ch_id})!")
            print(f"   API Response: {err}")
            print(f"   Ensure the channel username/ID is correct and bot is added to {ch_id}.")
            print("**********************************************************************\n")
            health_status["ok"] = False
            health_status["channels"][ch_name] = {"ok": False, "error": err}

    return health_status


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
    base_url = load_env_var("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    url = f"{base_url.rstrip('/')}/bot{bot_token}/sendMessage"
    opener = get_telegram_opener()
    
    # Try sending with Markdown first; fallback to raw text if markup parsing errors occur
    for parse_mode in ["Markdown", None]:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with opener.open(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            if parse_mode == "Markdown":
                continue
            return {"ok": False, "description": err_body}
        except (TimeoutError, urllib.error.URLError) as e:
            return {"ok": False, "description": f"Connection/SSL Timeout to Telegram API: {e}"}
        except Exception as e:
            return {"ok": False, "description": str(e)}

    return {"ok": False, "description": "Unknown error sending message"}


def send_telegram_photo(bot_token: str, chat_id: str, photo_url: str, caption: str) -> dict:
    """Send photo with caption to Telegram channel, with automatic fallback to text message."""
    if not photo_url or not photo_url.startswith("http"):
        return send_telegram_message(bot_token, chat_id, caption)

    base_url = load_env_var("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    url = f"{base_url.rstrip('/')}/bot{bot_token}/sendPhoto"
    opener = get_telegram_opener()

    # Telegram caption length limit is 1024 characters
    truncated_caption = caption[:1020] if len(caption) > 1020 else caption

    for parse_mode in ["Markdown", None]:
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": truncated_caption
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with opener.open(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("ok"):
                    return res
        except urllib.error.HTTPError as e:
            if parse_mode == "Markdown":
                continue
            # If photo fails, fallback to sendMessage
            print(f"  [!] Photo send failed, falling back to standard text message...")
            return send_telegram_message(bot_token, chat_id, caption)
        except Exception:
            return send_telegram_message(bot_token, chat_id, caption)

    return send_telegram_message(bot_token, chat_id, caption)


def get_published_archive_records(service, spreadsheet_id: str) -> tuple:
    """Fetches all published URLs and message IDs from Published_Archive for Point B Dedup."""
    published_urls = set()
    published_ids = set()
    try:
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="'Published_Archive'!A2:E"
        ).execute()
        rows = res.get("values", [])
        for r in rows:
            if len(r) > 0 and r[0]:  # post_id
                published_ids.add(r[0].strip())
            if len(r) > 4 and r[4]:  # source_url
                published_urls.add(r[4].strip().lower().rstrip("/"))
    except Exception as e:
        print(f"[!] Note: Could not query Published_Archive: {e}")
    return published_urls, published_ids


def broadcast_to_target_channels(
    bot_token: str,
    channel_1_id: str,
    channel_2_id: str,
    ch1_paused: bool,
    ch2_paused: bool,
    post_target: str,
    clean_text: str,
    image_url: str = ""
) -> tuple:
    """
    Broadcasts a post to designated channel(s) based on post_target and pause flags.
    Enforces a 10-30s delay if broadcasting to both channel 1 and channel 2.
    Returns (success_bool, list_of_message_ids, description_or_error).
    """
    target = (post_target or "BOTH").strip().upper()
    if target not in ["BOTH", "CHANNEL_1", "CHANNEL_2"]:
        target = "BOTH"

    destinations = []
    if target in ["BOTH", "CHANNEL_1"]:
        if ch1_paused:
            print("  [PAUSED] ⏸️ Channel 1 is paused (CHANNEL_1_PAUSED=true). Skipping Channel 1.")
        elif not channel_1_id:
            print("  [SKIP] Channel 1 is not configured in .env.")
        else:
            destinations.append(("Channel 1", channel_1_id))

    if target in ["BOTH", "CHANNEL_2"]:
        if ch2_paused:
            print("  [PAUSED] ⏸️ Channel 2 is paused (CHANNEL_2_PAUSED=true). Skipping Channel 2.")
        elif not channel_2_id:
            print("  [SKIP] Channel 2 is not configured in .env (TELEGRAM_CHANNEL_2_ID).")
        else:
            destinations.append(("Channel 2", channel_2_id))

    if not destinations:
        return False, [], "No active channels selected or all targeted channels are paused."

    msg_ids = []
    errors = []

    for i, (ch_label, ch_id) in enumerate(destinations):
        # Add 10-30s delay between Channel 1 and Channel 2 for the same post
        if i > 0:
            delay = random.randint(10, 25)
            print(f"  [DELAY] ⏳ Pausing {delay}s between broadcasting to {destinations[i-1][0]} and {ch_label}...")
            time.sleep(delay)

        print(f"  [+] Broadcasting to {ch_label} ({ch_id})...")
        if image_url:
            res = send_telegram_photo(bot_token, ch_id, image_url, clean_text)
        else:
            res = send_telegram_message(bot_token, ch_id, clean_text)

        if res.get("ok"):
            m_id = res.get("result", {}).get("message_id", "")
            print(f"  [SUCCESS] Published to {ch_label}! Message ID: #{m_id}")
            msg_ids.append(f"{ch_label}:{m_id}")
        else:
            err_desc = res.get("description", "Unknown error")
            print(f"  [!] {ch_label} Telegram error: {err_desc}")
            errors.append(f"{ch_label}: {err_desc}")

    # Success if at least one destination was published successfully
    if msg_ids:
        return True, msg_ids, ", ".join(errors) if errors else "OK"
    return False, [], "; ".join(errors) if errors else "All channel sends failed"


def publish_approved_content(credentials_path: str, spreadsheet_id: str, limit: int = 1, prune_published: bool = False):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from process_ai_content import validate_ai_response

    bot_token = load_env_var("TELEGRAM_BOT_TOKEN")
    channel_1_id = load_env_var("TELEGRAM_CHANNEL_1_ID") or load_env_var("TELEGRAM_CHANNEL_ID")
    channel_2_id = load_env_var("TELEGRAM_CHANNEL_2_ID")
    ch1_paused = load_env_var("CHANNEL_1_PAUSED", "false").lower() in ["true", "1", "yes"]
    ch2_paused = load_env_var("CHANNEL_2_PAUSED", "false").lower() in ["true", "1", "yes"]
    auto_prune = load_env_var("AUTO_PRUNE_PUBLISHED", "true").lower() in ["true", "1", "yes"] or prune_published

    if not bot_token or not (channel_1_id or channel_2_id):
        print("\n[!] Note: TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set in .env.")
        return

    # Bot permission health-check before publishing cycle
    print("\n[+] Running Bot Permission Health-Check...")
    check_bot_permissions(bot_token, channel_1_id, channel_2_id)

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    # Point B Dedup: Load Published_Archive records
    archived_urls, archived_ids = get_published_archive_records(service, spreadsheet_id)

    print(f"\n[+] Scanning Content_Queue for APPROVED items ready to publish...")
    res = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A2:N"
    ).execute()
    rows = res.get("values", [])

    if not rows:
        print("[OK] No rows found in Content_Queue.")
        return

    published_count = 0
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for idx, row in enumerate(rows, start=2):
        if published_count >= limit:
            break

        # Schema: id(0), source_title(1), source_url(2), topic_pillar(3), raw_text(4), ai_summary(5), telegram_post_text(6), status(7), quality_score(8), created_at(9), scheduled_at(10), published_at(11), error_log(12), post_target(13)
        status = row[7] if len(row) > 7 else ""
        published_at = row[11] if len(row) > 11 else ""
        post_id = row[0] if len(row) > 0 else ""
        title = row[1] if len(row) > 1 else ""
        source_url = row[2] if len(row) > 2 else ""
        pillar = row[3] if len(row) > 3 else "TECH_DEVELOPMENT"
        post_text = row[6] if len(row) > 6 else ""
        post_target = row[13] if len(row) > 13 and row[13] else "BOTH"

        # FIX 2 (Point B Filter): Only process if status is strictly APPROVED and not already published
        if status != "APPROVED" or published_at:
            continue

        # Check if already archived
        clean_url_key = source_url.strip().lower().rstrip("/")
        if (post_id and post_id in archived_ids) or (clean_url_key and clean_url_key in archived_urls):
            print(f"  [Point B Dedup] Row {idx} (\"{title[:40]}\") already exists in Published_Archive. Updating status to PUBLISHED.")
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'Content_Queue'!H{idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [["PUBLISHED"]]}
            ).execute()
            continue

        if not post_text or not post_text.strip():
            print(f"  [!] Row {idx} (\"{title[:40]}\") has empty post text. Skipping broadcast.")
            continue

        # Strict validation gate check
        is_valid, err_reason, clean_broadcast_text, _ = validate_ai_response(post_text, title, source_url, pillar)
        if not is_valid:
            print(f"  [!] ❌ Row {idx} (\"{title[:40]}\") failed validation gate: {err_reason}. Rejecting row.")
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'Content_Queue'!H{idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [["REJECTED_VALIDATION"]]}
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'Content_Queue'!M{idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [[f"Publish Validation Failed: {err_reason}"]]}
            ).execute()
            continue

        # Check if an image URL is attached
        raw_content = row[4] if len(row) > 4 else ""
        img_match = re.search(r'\[IMAGE:\s*([^\]]+)\]', raw_content)
        image_url = img_match.group(1).strip() if img_match else ""

        print(f"\n[+] Broadcasting post #{published_count + 1} [Target: {post_target}]...")
        print(f"    Title: \"{title[:60]}\"")
        if image_url:
            print(f"    Attached Image: {image_url}")

        success, msg_ids, err_desc = broadcast_to_target_channels(
            bot_token=bot_token,
            channel_1_id=channel_1_id,
            channel_2_id=channel_2_id,
            ch1_paused=ch1_paused,
            ch2_paused=ch2_paused,
            post_target=post_target,
            clean_text=clean_broadcast_text,
            image_url=image_url
        )
        
        if success:
            combined_msg_id = ", ".join(msg_ids)
            print(f"  [SUCCESS] Published to Telegram! Message(s): {combined_msg_id}")

            # 1. Update Content_Queue row to PUBLISHED
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'Content_Queue'!H{idx}:L{idx}",
                valueInputOption="USER_ENTERED",
                body={
                    "values": [["PUBLISHED", row[8] if len(row) > 8 else 0.9, row[9] if len(row) > 9 else "", now_iso, now_iso]]
                }
            ).execute()

            # 2. Append to Published_Archive
            archive_row = [
                post_id,
                combined_msg_id,
                pillar,
                clean_broadcast_text,
                source_url,
                now_iso,
                0,  # views_count
                0,  # forwards_count
                0   # reactions_count
            ]
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range="'Published_Archive'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [archive_row]}
            ).execute()

            # Reserve in memory
            archived_urls.add(clean_url_key)
            archived_ids.add(post_id)
            published_count += 1
        else:
            print(f"  [!] Broadcast failed: {err_desc}")

    print(f"\n[SUMMARY] Successfully published {published_count} post(s) to Telegram!\n")


def main():
    parser = argparse.ArgumentParser(description="Publish approved posts to Telegram channel")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json")
    parser.add_argument("--sheet-id", "-s", default="1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--prune", action="store_true", help="Prune published rows from Content_Queue")
    parser.add_argument("--health-check", action="store_true", help="Run bot permission health-check only")

    args = parser.parse_args()

    if args.health_check:
        bot_token = load_env_var("TELEGRAM_BOT_TOKEN")
        ch1 = load_env_var("TELEGRAM_CHANNEL_1_ID") or load_env_var("TELEGRAM_CHANNEL_ID")
        ch2 = load_env_var("TELEGRAM_CHANNEL_2_ID")
        check_bot_permissions(bot_token, ch1, ch2)
        return

    publish_approved_content(args.credentials, args.sheet_id, args.limit, args.prune)


if __name__ == "__main__":
    main()
