"""
Telegram Publisher for Telegram AI Content Pipeline.

Reads APPROVED items from Content_Queue in Google Sheets, broadcasts the post
to your Telegram channel via the Telegram Bot API, archives the record in
Published_Archive, and updates or prunes the row in Content_Queue.

Usage:
    python scripts/publish_telegram.py --sheet-id 1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE
"""

import os
import sys
import json
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


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
    base_url = load_env_var("TELEGRAM_API_BASE_URL", "https://api.telegram.org")
    url = f"{base_url.rstrip('/')}/bot{bot_token}/sendMessage"
    
    proxy = load_env_var("HTTPS_PROXY") or load_env_var("HTTP_PROXY")
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    
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

    proxy = load_env_var("HTTPS_PROXY") or load_env_var("HTTP_PROXY")
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

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


def publish_approved_content(credentials_path: str, spreadsheet_id: str, limit: int = 1, prune_published: bool = False):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from process_ai_content import validate_ai_response, format_to_clean_telegram_post

    bot_token = load_env_var("TELEGRAM_BOT_TOKEN")
    channel_id = load_env_var("TELEGRAM_CHANNEL_ID")
    auto_prune = load_env_var("AUTO_PRUNE_PUBLISHED", "true").lower() in ["true", "1", "yes"] or prune_published

    if not bot_token or not channel_id:
        print("\n[!] Note: TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set in .env.")
        return

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
        range="'Content_Queue'!A2:M"
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

        # Schema: id(0), source_title(1), source_url(2), topic_pillar(3), raw_text(4), ai_summary(5), telegram_post_text(6), status(7), quality_score(8), created_at(9), scheduled_at(10), published_at(11)
        status = row[7] if len(row) > 7 else ""
        published_at = row[11] if len(row) > 11 else ""
        post_id = row[0] if len(row) > 0 else ""
        title = row[1] if len(row) > 1 else ""
        source_url = row[2] if len(row) > 2 else ""
        pillar = row[3] if len(row) > 3 else "TECH_DEVELOPMENT"
        post_text = row[6] if len(row) > 6 else ""

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

        if not post_text:
            continue

        # FIX 1 & 4: Ensure content is clean and validated
        is_valid, err_reason, clean_broadcast_text, _ = validate_ai_response(post_text, title, source_url, pillar)
        if not is_valid:
            # Reformat fallback
            clean_broadcast_text = format_to_clean_telegram_post(post_text, title, source_url, pillar)

        # Check if an image URL is attached
        raw_content = row[4] if len(row) > 4 else ""
        img_match = re.search(r'\[IMAGE:\s*([^\]]+)\]', raw_content)
        image_url = img_match.group(1).strip() if img_match else ""

        print(f"\n[+] Broadcasting post #{published_count + 1} to Telegram channel {channel_id}...")
        print(f"    Title: \"{title[:60]}\"")
        if image_url:
            print(f"    Attached Image: {image_url}")
            tg_res = send_telegram_photo(bot_token, channel_id, image_url, clean_broadcast_text)
        else:
            tg_res = send_telegram_message(bot_token, channel_id, clean_broadcast_text)
        
        if tg_res.get("ok"):
            msg_id = tg_res.get("result", {}).get("message_id", "")
            print(f"  [SUCCESS] Published to Telegram! Message ID: #{msg_id}")

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
                str(msg_id),
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
            desc = tg_res.get("description", "Unknown error")
            print(f"  [!] Telegram error: {desc}")
            print("  💡 Tip: Make sure your VPN is active and the bot is an Administrator in @maazzalii!")

    print(f"\n[SUMMARY] Successfully published {published_count} post(s) to Telegram!\n")


def main():
    parser = argparse.ArgumentParser(description="Publish approved posts to Telegram channel")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json")
    parser.add_argument("--sheet-id", "-s", default="1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--prune", action="store_true", help="Prune published rows from Content_Queue")

    args = parser.parse_args()
    publish_approved_content(args.credentials, args.sheet_id, args.limit, args.prune)


if __name__ == "__main__":
    main()
