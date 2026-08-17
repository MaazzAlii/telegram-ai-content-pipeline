"""
Telegram Publisher for Telegram AI Content Pipeline.

Reads APPROVED items from Content_Queue in Google Sheets, broadcasts the post
to your Telegram channel via the Telegram Bot API with formatted HTML/Markdown,
moves the record to Published_Archive, and updates pipeline metrics.

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
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def publish_approved_content(credentials_path: str, spreadsheet_id: str, limit: int = 1):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    bot_token = load_env_var("TELEGRAM_BOT_TOKEN")
    channel_id = load_env_var("TELEGRAM_CHANNEL_ID")

    if not bot_token or not channel_id:
        print("\n[!] Note: TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set in .env yet.")
        print("    Create a bot with @BotFather on Telegram and add your bot token & channel ID to .env to publish live posts.")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

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

        # Schema: id(0), source_title(1), source_url(2), topic_pillar(3), raw_text(4), ai_summary(5), telegram_post_text(6), status(7)
        status = row[7] if len(row) > 7 else ""
        if status == "APPROVED":
            post_id = row[0] if len(row) > 0 else ""
            source_url = row[2] if len(row) > 2 else ""
            pillar = row[3] if len(row) > 3 else ""
            post_text = row[6] if len(row) > 6 else ""

            if not post_text:
                continue

            print(f"\n[+] Broadcasting post to Telegram channel {channel_id}...")
            try:
                tg_res = send_telegram_message(bot_token, channel_id, post_text)
                if tg_res.get("ok"):
                    msg_id = tg_res.get("result", {}).get("message_id", "")
                    print(f"  [OK] Successfully published message ID #{msg_id}!")

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
                        post_text,
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

                    published_count += 1
                else:
                    print(f"  [!] Telegram error: {tg_res}")
            except Exception as e:
                print(f"  [!] Failed publishing to Telegram: {e}")

    print(f"\n[SUCCESS] Published {published_count} post(s) to Telegram!\n")


def main():
    parser = argparse.ArgumentParser(description="Publish approved posts to Telegram channel")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json")
    parser.add_argument("--sheet-id", "-s", default="1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")
    parser.add_argument("--limit", type=int, default=1)

    args = parser.parse_args()
    publish_approved_content(args.credentials, args.sheet_id, args.limit)


if __name__ == "__main__":
    main()
