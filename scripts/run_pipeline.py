"""
Telegram AI Content Pipeline - Master End-to-End Runner.

Coordinates the entire pipeline:
1. Ingests fresh tech & AI news from curated RSS feeds into Google Sheets Content_Queue.
2. Formats pending queue items using Gemini AI and pillar prompt templates.
3. Publishes approved content to your Telegram Channel.
4. Archives published posts and tracks metrics.

Commands:
    python scripts/run_pipeline.py --all           # Run full cycle
    python scripts/run_pipeline.py --ingest        # Ingest new articles
    python scripts/run_pipeline.py --process-ai    # Auto-format & approve pending items
    python scripts/run_pipeline.py --publish       # Publish approved posts to Telegram
    python scripts/run_pipeline.py --clear-queue   # Wipe all old items from queue
"""

import os
import sys
import argparse
from pathlib import Path

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from fetch_feeds import ingest_to_sheets
from process_ai_content import process_queue
from publish_telegram import publish_approved_content

CREDENTIALS_FILE = "telegram-ai-pipeline-85177bbe5835.json"
SPREADSHEET_ID = "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE"


def clear_content_queue(credentials_path: str, spreadsheet_id: str):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    print(f"\n[+] Connecting to Google Sheets to clear Content_Queue...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    # Clear everything below header row (row 2 onwards)
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A2:M"
    ).execute()

    print("[SUCCESS] Cleared all old data from Content_Queue! Header row preserved.\n")


def run_pipeline(do_ingest: bool, do_ai: bool, do_publish: bool):
    print("=" * 70)
    print("🚀 Telegram AI Content Pipeline — Automated Execution")
    print("=" * 70)

    if do_ingest:
        print("\n[STEP 1] 📥 INGESTION: Fetching RSS feeds into Google Sheets...")
        try:
            ingest_to_sheets(CREDENTIALS_FILE, SPREADSHEET_ID, max_per_feed=2)
        except Exception as e:
            print(f"[!] Ingestion Error: {e}")

    if do_ai:
        print("\n[STEP 2] 🧠 AI PROCESSING: Generating Telegram posts with Gemini...")
        try:
            process_queue(CREDENTIALS_FILE, SPREADSHEET_ID, limit=5)
        except Exception as e:
            print(f"[!] AI Processing Error: {e}")

    if do_publish:
        print("\n[STEP 3] 📢 PUBLISHING: Broadcasting approved posts to Telegram...")
        try:
            publish_approved_content(CREDENTIALS_FILE, SPREADSHEET_ID, limit=1)
        except Exception as e:
            print(f"[!] Publishing Error: {e}")

    print("\n" + "=" * 70)
    print("✨ Pipeline run cycle completed!")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Run Telegram AI Content Pipeline")
    parser.add_argument("--all", action="store_true", help="Run full cycle (Ingest -> AI -> Publish)")
    parser.add_argument("--ingest", action="store_true", help="Run RSS Ingestion only")
    parser.add_argument("--process-ai", action="store_true", help="Run AI Content Processing only")
    parser.add_argument("--publish", action="store_true", help="Publish approved content only")
    parser.add_argument("--clear-queue", action="store_true", help="Wipe all old rows from Content_Queue in Sheet")

    args = parser.parse_args()

    if args.clear_queue:
        clear_content_queue(CREDENTIALS_FILE, SPREADSHEET_ID)
        return

    if not any([args.all, args.ingest, args.process_ai, args.publish]):
        # Default to full run
        run_pipeline(do_ingest=True, do_ai=True, do_publish=True)
    else:
        run_pipeline(
            do_ingest=args.all or args.ingest,
            do_ai=args.all or args.process_ai,
            do_publish=args.all or args.publish
        )


if __name__ == "__main__":
    main()
