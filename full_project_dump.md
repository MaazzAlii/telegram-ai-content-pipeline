--- FILE: requirements.txt ---
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=1.0.0
pyyaml>=6.0
requests>=2.31.0
python-dotenv>=1.0.0


--- FILE: .env.example ---
# ==============================================================================
# Telegram AI Content Pipeline — Environment Configuration Template
# Copy this file to .env and fill in your values. DO NOT commit .env to git.
# ==============================================================================

# --- n8n Service Configuration ---
N8N_PORT=5678
N8N_HOST=localhost
N8N_PROTOCOL=http
N8N_DEFAULT_LOCALE=en
GENERIC_TIMEZONE=UTC
N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
EXECUTIONS_DATA_PRUNE=true
EXECUTIONS_DATA_MAX_AGE=168

# --- Telegram Bot & Channel ---
# Create a bot with @BotFather on Telegram, paste token below
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
# Channel username (e.g., @my_ai_channel) or Channel ID (e.g., -1001234567890)
TELEGRAM_CHANNEL_ID=@your_channel_username_or_id

# --- Google Sheets ---
# The ID extracted from your Google Sheet URL: https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
GOOGLE_SHEET_ID=your_google_spreadsheet_id_here

# --- Primary AI Provider: Google Gemini Multi-Key Rotation Pool ---
# Comma-separated list of Gemini API keys. The system rotates through keys if rate-limited.
GEMINI_API_KEYS=gemini_key_1,gemini_key_2,gemini_key_3

# --- Fallback Tier 1: Mistral AI ---
# Used automatically if all Gemini keys exceed daily quotas or rate limits
MISTRAL_API_KEY=your_mistral_api_key_here

# --- Fallback Tier 2: Groq Cloud (Ultra-Fast Llama 3) ---
# Used automatically if Gemini and Mistral fail
GROQ_API_KEY=your_groq_api_key_here


--- FILE: docker-compose.yml ---
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n:latest
    container_name: telegram_ai_n8n
    restart: unless-stopped
    ports:
      - "${N8N_PORT:-5678}:5678"
    environment:
      - N8N_HOST=${N8N_HOST:-localhost}
      - N8N_PORT=${N8N_PORT:-5678}
      - N8N_PROTOCOL=${N8N_PROTOCOL:-http}
      - NODE_ENV=production
      - WEBHOOK_URL=${N8N_PROTOCOL:-http}://${N8N_HOST:-localhost}:${N8N_PORT:-5678}/
      - GENERIC_TIMEZONE=${GENERIC_TIMEZONE:-UTC}
      - EXECUTIONS_DATA_PRUNE=true
      - EXECUTIONS_DATA_MAX_AGE=168
      - N8N_DEFAULT_LOCALE=en
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  n8n_data:
    name: telegram_ai_n8n_data


--- FILE: render.yaml ---
services:
  - type: web
    name: telegram-ai-content-pipeline
    env: python
    region: frankfurt
    plan: free
    buildCommand: pip install -r scripts/requirements.txt
    startCommand: python scripts/dashboard_server.py
    autoDeploy: true
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.8
      - key: GOOGLE_SHEET_ID
        value: 1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: TELEGRAM_CHANNEL_ID
        value: "@maazzalii"
      - key: GEMINI_API_KEYS
        sync: false
      - key: MISTRAL_API_KEY
        sync: false
      - key: GROQ_API_KEY
        sync: false
      - key: GOOGLE_SERVICE_ACCOUNT_JSON
        sync: false
      - key: AUTO_APPROVE
        value: "true"


--- FILE: config/sources.yaml ---
# Curated Source Feeds for Telegram AI Content Pipeline
# Trust Levels:
#   1 = Official / Primary Research / Direct Releases
#   2 = Tier-1 Tech Journalism
#   3 = Community & Aggregators

sources:
  ai_industry_startups:
    - name: "OpenAI News"
      url: "https://openai.com/news/rss.xml"
      trust_level: 1
    - name: "Google AI Blog"
      url: "https://blog.google/technology/ai/rss/"
      trust_level: 1
    - name: "MIT Technology Review AI"
      url: "https://www.technologyreview.com/topic/artificial-intelligence/feed"
      trust_level: 2
    - name: "TechCrunch AI"
      url: "https://techcrunch.com/category/artificial-intelligence/feed/"
      trust_level: 2
    - name: "Hugging Face Blog"
      url: "https://huggingface.co/blog/feed.xml"
      trust_level: 1

  ai_tools:
    - name: "TechCrunch Startups & Apps"
      url: "https://techcrunch.com/category/startups/feed/"
      trust_level: 2
    - name: "The Verge Tech"
      url: "https://www.theverge.com/rss/index.xml"
      trust_level: 2

  cybersecurity:
    - name: "BleepingComputer"
      url: "https://www.bleepingcomputer.com/feed/"
      trust_level: 2
    - name: "The Hacker News"
      url: "https://feeds.feedburner.com/TheHackersNews"
      trust_level: 2

  learning_resources:
    - name: "GitHub Trending Today"
      url: "https://github-rss.alexi.sh/trending/daily/python"
      trust_level: 2

  tech_development:
    - name: "Hacker News Frontpage"
      url: "https://news.ycombinator.com/rss"
      trust_level: 3
    - name: "Ars Technica"
      url: "https://feeds.arstechnica.com/arstechnica/index"
      trust_level: 2


--- FILE: config/sheets_schema.json ---
{
  "spreadsheet_title": "Telegram Content Pipeline",
  "tabs": {
    "Content_Queue": {
      "description": "Incoming and pending content items waiting for AI processing, review, and scheduling.",
      "headers": [
        "id",
        "source_title",
        "source_url",
        "topic_pillar",
        "raw_text",
        "ai_summary",
        "telegram_post_text",
        "status",
        "quality_score",
        "created_at",
        "scheduled_at",
        "published_at",
        "error_log"
      ],
      "validations": {
        "status": ["PENDING", "APPROVED", "REJECTED", "PUBLISHED", "FAILED"],
        "topic_pillar": [
          "AI_TOOLS",
          "AI_INDUSTRY_STARTUPS",
          "CYBERSECURITY",
          "LEARNING_RESOURCES",
          "TECH_DEVELOPMENT"
        ]
      }
    },
    "Topic_Pillars": {
      "description": "Configuration for content categories, prompt mappings, and scheduling weights.",
      "headers": [
        "pillar_id",
        "pillar_name",
        "description",
        "weight",
        "is_active",
        "prompt_template_file"
      ],
      "default_data": [
        [
          "AI_TOOLS",
          "AI Tools & Product Launches",
          "Breakdowns and workflows for newly released AI tools and practical productivity hacks",
          0.25,
          "TRUE",
          "ai_tools.md"
        ],
        [
          "AI_INDUSTRY_STARTUPS",
          "AI Industry & Startup News",
          "Major AI developments, model releases, venture funding, and market movements",
          0.25,
          "TRUE",
          "ai_industry_startups.md"
        ],
        [
          "CYBERSECURITY",
          "Cybersecurity & Threat Intelligence",
          "Zero-day vulnerabilities, breach alerts, defensive tactics, and security research",
          0.20,
          "TRUE",
          "cybersecurity.md"
        ],
        [
          "LEARNING_RESOURCES",
          "Curated Learning Resources & Roadmaps",
          "Free courses, GitHub repos, cheat sheets, and technical deep-dives",
          0.15,
          "TRUE",
          "learning_resources.md"
        ],
        [
          "TECH_DEVELOPMENT",
          "Technology Trends & Development",
          "Software architecture, frameworks, cloud native, DevOps, and backend engineering",
          0.15,
          "TRUE",
          "technology.md"
        ]
      ]
    },
    "Published_Archive": {
      "description": "Archive of all successfully published Telegram messages with message IDs and engagement tracking.",
      "headers": [
        "id",
        "telegram_message_id",
        "topic_pillar",
        "post_text",
        "source_url",
        "published_at",
        "views_count",
        "forwards_count",
        "reactions_count"
      ]
    },
    "Pipeline_Metrics": {
      "description": "Daily aggregated execution statistics for pipeline health, ingestion rates, and error tracking.",
      "headers": [
        "date",
        "total_ingested",
        "total_processed",
        "approved_count",
        "published_count",
        "failed_count",
        "avg_processing_time_sec",
        "last_health_status"
      ]
    }
  }
}


--- FILE: scripts/run_pipeline.py ---
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
BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from fetch_feeds import ingest_to_sheets
from process_ai_content import process_queue
from publish_telegram import publish_approved_content

CREDENTIALS_FILE = "telegram-ai-pipeline-85177bbe5835.json"
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")

# Auto-create credentials JSON from environment variable if running on Render/Cloud
if not (BASE_DIR / CREDENTIALS_FILE).exists() and os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
    with open(BASE_DIR / CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        f.write(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])


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


--- FILE: scripts/dashboard_server.py ---
"""
Enhanced Dashboard Server & Background Scheduler for Telegram AI Content Pipeline.

Features:
- Individual post editing (insert referral links, edit text).
- Single-click row publishing to Telegram.
- Row rejection / dismissal.
- Built-in Auto-Pilot Scheduler (auto-posts 2-3 times/day without manual clicking).
- Topic Pillar filtering and search.
"""

import os
import sys
import json
import time
import subprocess
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
SCRIPTS_DIR = BASE_DIR / "scripts"
CREDENTIALS_FILE = "telegram-ai-pipeline-85177bbe5835.json"
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")

# Auto-create credentials JSON from environment variable if running on Render/Cloud
if not (BASE_DIR / CREDENTIALS_FILE).exists() and os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
    with open(BASE_DIR / CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        f.write(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])

LATEST_LOGS = ["Dashboard control center active. Auto-Pilot ready."]

AUTOPILOT_CONFIG = {
    "enabled": False,
    "interval_hours": 6,  # 4 times/day max
    "max_posts_per_day": 3,
    "last_run_time": None
}


def add_log(msg: str):
    global LATEST_LOGS
    LATEST_LOGS.append(msg)
    if len(LATEST_LOGS) > 120:
        LATEST_LOGS.pop(0)


def run_pipeline_action_async(action: str):
    def worker():
        cmd = [sys.executable, "-u", str(SCRIPTS_DIR / "run_pipeline.py")]
        if action == "all":
            cmd.append("--all")
        elif action == "ingest":
            cmd.append("--ingest")
        elif action == "process-ai":
            cmd.append("--process-ai")
        elif action == "publish":
            cmd.append("--publish")
        elif action == "clear-queue":
            cmd.append("--clear-queue")

        add_log(f"\n[ACTION TRIGGERED] Running: {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            for line in proc.stdout:
                line_str = line.strip()
                if line_str:
                    add_log(line_str)
            proc.wait()
            add_log(f"[ACTION COMPLETE] Exit code: {proc.returncode}\n")
        except Exception as e:
            add_log(f"[ACTION ERROR] {e}\n")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


def get_sheets_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = BASE_DIR / CREDENTIALS_FILE
    if not creds_path.exists():
        raise FileNotFoundError(f"Credentials not found at {creds_path}")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=scopes
    )
    return build("sheets", "v4", credentials=creds)


def fetch_sheet_queue() -> dict:
    try:
        import re
        service = get_sheets_service()
        res = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="'Content_Queue'!A2:M"
        ).execute()
        rows = res.get("values", [])

        items = []
        pending_count = 0
        approved_count = 0
        published_count = 0
        rejected_count = 0

        for idx, r in enumerate(rows, start=2):
            status = r[7].strip() if len(r) > 7 and r[7] else "PENDING"
            if status == "PENDING":
                pending_count += 1
            elif status == "APPROVED":
                approved_count += 1
            elif status == "PUBLISHED":
                published_count += 1
            elif status == "REJECTED":
                rejected_count += 1

            raw_txt = r[4] if len(r) > 4 else ""
            img_match = re.search(r'\[IMAGE:\s*([^\]]+)\]', raw_txt)
            image_url = img_match.group(1).strip() if img_match else ""

            items.append({
                "row_index": idx,
                "id": r[0] if len(r) > 0 else "",
                "source_title": r[1] if len(r) > 1 else "",
                "source_url": r[2] if len(r) > 2 else "",
                "topic_pillar": r[3] if len(r) > 3 else "TECH_DEVELOPMENT",
                "raw_text": raw_txt,
                "image_url": image_url,
                "ai_summary": r[5] if len(r) > 5 else "",
                "telegram_post_text": r[6] if len(r) > 6 else "",
                "status": status,
                "created_at": r[9] if len(r) > 9 else ""
            })

        return {
            "total": len(items),
            "pending": pending_count,
            "approved": approved_count,
            "published": published_count,
            "rejected": rejected_count,
            "autopilot": AUTOPILOT_CONFIG,
            "items": items[::-1]  # Newest first
        }
    except Exception as e:
        return {"error": str(e), "items": [], "total": 0, "pending": 0, "approved": 0, "published": 0, "rejected": 0, "autopilot": AUTOPILOT_CONFIG}


def set_single_post_status(row_index: int, new_status: str) -> bool:
    """Instantly set post status to APPROVED, REJECTED, or PENDING."""
    try:
        service = get_sheets_service()
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'Content_Queue'!H{row_index}",
            valueInputOption="USER_ENTERED",
            body={"values": [[new_status]]}
        ).execute()
        add_log(f"[STATUS UPDATE] Row #{row_index} status updated to: {new_status}")
        return True
    except Exception as e:
        add_log(f"[STATUS UPDATE ERROR] Row #{row_index}: {e}")
        return False


def update_single_post(row_index: int, new_text: str, new_status: str = "APPROVED", new_image_url: str = "") -> bool:
    try:
        service = get_sheets_service()
        # Update text (col G) and status (col H)
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'Content_Queue'!G{row_index}:H{row_index}",
            valueInputOption="USER_ENTERED",
            body={"values": [[new_text, new_status]]}
        ).execute()

        # If image URL provided, update raw_text column E with [IMAGE: ...] tag
        if new_image_url:
            res = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'Content_Queue'!E{row_index}"
            ).execute()
            existing_raw = res.get("values", [[""]])[0][0] if res.get("values") else ""
            import re
            cleaned_raw = re.sub(r'\[IMAGE:\s*[^\]]+\]\s*', '', existing_raw).strip()
            updated_raw = f"[IMAGE: {new_image_url}]\n{cleaned_raw}"
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'Content_Queue'!E{row_index}",
                valueInputOption="USER_ENTERED",
                body={"values": [[updated_raw]]}
            ).execute()

        add_log(f"[SHEET UPDATE] Row {row_index} updated & set to {new_status}")
        return True
    except Exception as e:
        add_log(f"[SHEET UPDATE ERROR] {e}")
        return False


def publish_single_post_by_row(row_index: int, post_text: str, source_url: str, pillar: str, post_id: str, image_url: str = ""):
    from process_ai_content import format_to_clean_telegram_post
    from publish_telegram import send_telegram_message, send_telegram_photo, load_env_var
    import datetime
    import re

    bot_token = load_env_var("TELEGRAM_BOT_TOKEN")
    channel_id = load_env_var("TELEGRAM_CHANNEL_ID")

    if not bot_token or not channel_id:
        return {"ok": False, "error": "Bot credentials missing in .env"}

    # Guard: check if already published
    service = get_sheets_service()
    try:
        cur_row = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'Content_Queue'!A{row_index}:M{row_index}"
        ).execute()
        vals = cur_row.get("values", [[]])[0]
        cur_status = vals[7] if len(vals) > 7 else ""
        if cur_status == "PUBLISHED":
            return {"ok": False, "error": "This post is already marked as PUBLISHED."}
    except Exception as e:
        add_log(f"[WARN] Could not check current row status: {e}")

    # Always sanitize raw text / JSON before sending
    clean_text = format_to_clean_telegram_post(post_text, "", source_url, pillar)

    # Check for image URL from argument or fetch from sheet
    if not image_url:
        try:
            res = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'Content_Queue'!E{row_index}"
            ).execute()
            raw_text = res.get("values", [[""]])[0][0] if res.get("values") else ""
            img_match = re.search(r'\[IMAGE:\s*([^\]]+)\]', raw_text)
            if img_match:
                image_url = img_match.group(1).strip()
        except Exception:
            pass

    add_log(f"\n[SINGLE PUBLISH] Broadcasting row {row_index} to {channel_id}...")
    if image_url:
        add_log(f"  Attached image: {image_url}")
        res = send_telegram_photo(bot_token, channel_id, image_url, clean_text)
    else:
        res = send_telegram_message(bot_token, channel_id, clean_text)
    
    if res.get("ok"):
        msg_id = res.get("result", {}).get("message_id", "")
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        add_log(f"  [SUCCESS] Message #{msg_id} published live to Telegram!")

        # Update sheet status immediately
        try:
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'Content_Queue'!H{row_index}:L{row_index}",
                valueInputOption="USER_ENTERED",
                body={"values": [["PUBLISHED", 0.95, "", now_iso, now_iso]]}
            ).execute()

            # Append to Published_Archive
            archive_row = [post_id, str(msg_id), pillar, clean_text, source_url, now_iso, 0, 0, 0]
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range="'Published_Archive'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [archive_row]}
            ).execute()
        except Exception as e:
            add_log(f"[ARCHIVE WARNING] {e}")

        return {"ok": True, "message_id": msg_id}
    else:
        err = res.get("description", "Unknown error")
        add_log(f"  [!] Failed to publish: {err}")
        return {"ok": False, "error": err}


def autopilot_worker():
    """Background daemon that auto-runs the pipeline every N hours when enabled."""
    while True:
        try:
            if AUTOPILOT_CONFIG.get("enabled"):
                add_log("⏰ [AUTO-PILOT] Triggering scheduled content cycle...")
                # Run full cycle (Ingest -> AI Format -> Publish 1 item)
                cmd = [sys.executable, "-u", str(SCRIPTS_DIR / "run_pipeline.py"), "--all"]
                proc = subprocess.run(
                    cmd,
                    cwd=str(BASE_DIR),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                add_log(f"[AUTO-PILOT COMPLETE] {proc.stdout[-200:] if proc.stdout else 'Done'}")
                AUTOPILOT_CONFIG["last_run_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Sleep interval (default: 4 hours = 14400s)
            interval_secs = max(3600, AUTOPILOT_CONFIG.get("interval_hours", 6) * 3600)
            time.sleep(interval_secs)
        except Exception as e:
            add_log(f"[AUTO-PILOT LOOP ERROR] {e}")
            time.sleep(60)


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.path = "/dashboard/index.html"
            return super().do_GET()

        if parsed.path == "/api/status":
            data = fetch_sheet_queue()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        if parsed.path == "/api/logs":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"logs": LATEST_LOGS}).encode("utf-8"))
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        payload = json.loads(body) if body else {}

        if parsed.path == "/api/run":
            action = payload.get("action", "all")
            run_pipeline_action_async(action)
            self._send_json({"status": "started", "action": action})
            return

        if parsed.path == "/api/set-status":
            row_idx = payload.get("row_index")
            new_status = payload.get("status", "APPROVED")
            ok = set_single_post_status(row_idx, new_status)
            self._send_json({"ok": ok, "row_index": row_idx, "status": new_status})
            return

        if parsed.path == "/api/fetch-topic":
            keyword = payload.get("keyword", "").strip()
            pillar = payload.get("pillar", "AI_INDUSTRY_STARTUPS")
            max_items = int(payload.get("max_items", 4))
            from fetch_feeds import fetch_by_keyword
            add_log(f"\n[TOPIC SEARCH] Searching live news for '{keyword}' [{pillar}]...")
            res = fetch_by_keyword(keyword, pillar, str(BASE_DIR / CREDENTIALS_FILE), SPREADSHEET_ID, max_items=max_items)
            if res.get("ok"):
                add_log(f"[TOPIC SUCCESS] Added {res.get('added', 0)} new articles for '{keyword}' to queue!")
            else:
                add_log(f"[TOPIC ERROR] {res.get('error')}")
            self._send_json(res)
            return

        if parsed.path == "/api/update-post":
            row_idx = payload.get("row_index")
            new_text = payload.get("text", "")
            new_status = payload.get("status", "APPROVED")
            new_image_url = payload.get("image_url", "")
            ok = update_single_post(row_idx, new_text, new_status, new_image_url)
            self._send_json({"ok": ok})
            return

        if parsed.path == "/api/publish-single":
            row_idx = payload.get("row_index")
            text = payload.get("text", "")
            url = payload.get("source_url", "")
            pillar = payload.get("topic_pillar", "TECH")
            post_id = payload.get("id", "")
            image_url = payload.get("image_url", "")
            res = publish_single_post_by_row(row_idx, text, url, pillar, post_id, image_url)
            self._send_json(res)
            return

        if parsed.path == "/api/toggle-autopilot":
            enabled = payload.get("enabled", False)
            hours = int(payload.get("interval_hours", 6))
            AUTOPILOT_CONFIG["enabled"] = enabled
            AUTOPILOT_CONFIG["interval_hours"] = hours
            add_log(f"[CONFIG] Auto-Pilot Scheduler set to: {'ON' if enabled else 'OFF'} (Every {hours}h)")
            self._send_json({"ok": True, "autopilot": AUTOPILOT_CONFIG})
            return

    def _send_json(self, data: dict):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


def run_server(port: int = 8080):
    # Start background auto-pilot thread
    t = threading.Thread(target=autopilot_worker, daemon=True)
    t.start()

    server_address = ("", port)
    os.chdir(str(BASE_DIR))
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"\n" + "=" * 60)
    print(f"🌟 Telegram AI Control Center & Auto-Pilot Running!")
    print(f"👉 Local Access:   http://localhost:{port}")
    print(f"👉 Mobile Access:  http://YOUR_LOCAL_IP:{port}")
    print("=" * 60 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    default_port = int(os.environ.get("PORT", 8080))
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=default_port)
    args = parser.parse_args()
    run_server(args.port)


--- FILE: scripts/fetch_feeds.py ---
"""
RSS & Content Feed Ingestor for Telegram AI Pipeline.

Parses active RSS feeds defined in config/sources.yaml, filters out duplicates
against the Google Sheet Content_Queue, and appends new pending items.
"""

import os
import sys
import uuid
import datetime
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import urllib.request
import re
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CONFIG_SOURCES = Path(__file__).resolve().parent.parent / "config" / "sources.yaml"

PILLAR_MAPPING = {
    "ai_industry_startups": "AI_INDUSTRY_STARTUPS",
    "ai_news": "AI_INDUSTRY_STARTUPS",
    "ai_tools": "AI_TOOLS",
    "cybersecurity": "CYBERSECURITY",
    "learning_resources": "LEARNING_RESOURCES",
    "tech_development": "TECH_DEVELOPMENT",
}


def clean_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    return " ".join(clean.split())


def load_categorized_sources() -> list:
    if not CONFIG_SOURCES.exists():
        raise FileNotFoundError(f"Config sources not found at {CONFIG_SOURCES}")
    with open(CONFIG_SOURCES, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    flat_sources = []
    sources_dict = data.get("sources", {})
    for category, feeds in sources_dict.items():
        pillar = PILLAR_MAPPING.get(category, "TECH_DEVELOPMENT")
        if isinstance(feeds, list):
            for feed in feeds:
                if isinstance(feed, dict):
                    feed["pillar"] = pillar
                    flat_sources.append(feed)
    return flat_sources


def extract_image_url(item_node, desc_text: str = "") -> str:
    """Extract image URL from RSS item enclosure, media tags, or description HTML."""
    try:
        # 1. Check enclosure tag with image type
        enclosure = item_node.find("enclosure")
        if enclosure is not None:
            enc_type = enclosure.attrib.get("type", "")
            enc_url = enclosure.attrib.get("url", "")
            if "image" in enc_type or enc_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                return enc_url

        # 2. Check media:content or media:thumbnail
        for media_tag in [
            "{http://search.yahoo.com/mrss/}content",
            "{http://search.yahoo.com/mrss/}thumbnail",
            "media:content",
            "media:thumbnail"
        ]:
            node = item_node.find(media_tag)
            if node is not None:
                media_url = node.attrib.get("url")
                if media_url:
                    return media_url

        # 3. Check itunes:image
        itunes_img = item_node.find("{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
        if itunes_img is not None and itunes_img.attrib.get("href"):
            return itunes_img.attrib.get("href")

        # 4. Extract from HTML description
        if desc_text:
            img_match = re.search(r'<img[^>]+src=["\'](https?://[^"\'>]+)["\']', desc_text, re.IGNORECASE)
            if img_match:
                candidate = img_match.group(1)
                if not candidate.endswith(("icon.png", "logo.png", "1x1.gif", "spacer.gif")):
                    return candidate
    except Exception:
        pass
    return ""


def fetch_rss_entries(feed_url: str, pillar: str, max_items: int = 3) -> list:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TelegramAIPipeline/1.0"}
    req = urllib.request.Request(feed_url, headers=headers)
    items = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
        
        root = ET.fromstring(content)
        channel = root.find("channel")
        if channel is not None:
            raw_items = channel.findall("item")
        else:
            raw_items = root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry")

        for item in raw_items[:max_items]:
            title = ""
            link = ""
            raw_desc = ""

            title_node = item.find("title")
            link_node = item.find("link")
            desc_node = item.find("description") or item.find("{http://purl.org/rss/1.0/modules/content/}encoded")

            if title_node is not None and title_node.text:
                title = clean_html(title_node.text)
            if link_node is not None:
                link = link_node.text.strip() if link_node.text else link_node.attrib.get("href", "")
            if desc_node is not None and desc_node.text:
                raw_desc = desc_node.text

            image_url = extract_image_url(item, raw_desc)
            clean_desc = clean_html(raw_desc)

            # Prefix raw_text with image metadata if found
            content_text = f"[IMAGE: {image_url}]\n{clean_desc[:1000]}" if image_url else (clean_desc[:1000] if clean_desc else title)

            if title and link:
                items.append({
                    "id": str(uuid.uuid4())[:8],
                    "source_title": title,
                    "source_url": link,
                    "topic_pillar": pillar,
                    "raw_text": content_text,
                    "image_url": image_url,
                    "status": "PENDING",
                    "quality_score": 0.85,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
    except Exception as e:
        print(f"  [!] Failed fetching {feed_url}: {e}")
    
    return items


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, hashes, and trailing slashes."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        # Remove common analytics parameters
        query_params = urllib.parse.parse_qsl(parsed.query)
        cleaned_params = [(k, v) for k, v in query_params if not k.startswith("utm_") and k not in ("ref", "cmpid", "source")]
        new_query = urllib.parse.urlencode(cleaned_params)
        clean_url = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            new_query,
            ""
        ))
        return clean_url
    except Exception:
        return url.strip().rstrip("/").lower()


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy duplicate detection."""
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]", "", title.lower())[:80]


def get_existing_records(service, spreadsheet_id: str) -> tuple:
    """Fetch all existing URLs and titles from both Content_Queue and Published_Archive to prevent duplicates."""
    existing_urls = set()
    existing_titles = set()

    # 1. Check Content_Queue (Col B: title, Col C: url)
    try:
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="'Content_Queue'!B2:C"
        ).execute()
        rows = res.get("values", [])
        for r in rows:
            if len(r) > 0 and r[0]:
                existing_titles.add(normalize_title(r[0]))
            if len(r) > 1 and r[1]:
                existing_urls.add(normalize_url(r[1]))
                existing_urls.add(r[1].strip())
    except Exception as e:
        print(f"[!] Note: Could not read Content_Queue: {e}")

    # 2. Check Published_Archive (Col E: source_url)
    try:
        res_arch = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="'Published_Archive'!D2:E"
        ).execute()
        rows_arch = res_arch.get("values", [])
        for r in rows_arch:
            if len(r) > 1 and r[1]:
                existing_urls.add(normalize_url(r[1]))
                existing_urls.add(r[1].strip())
    except Exception as e:
        pass

    return existing_urls, existing_titles


def fetch_by_keyword(keyword: str, pillar: str, credentials_path: str, spreadsheet_id: str, max_items: int = 5) -> dict:
    """Fetch live news from Google News RSS for any custom keyword or search topic."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if not keyword or not keyword.strip():
        return {"ok": False, "error": "Search keyword cannot be empty", "added": 0}

    keyword = keyword.strip()
    encoded_query = urllib.parse.quote(keyword)
    feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    print(f"\n[+] Searching news for custom topic: '{keyword}' (Pillar: {pillar})...")
    entries = fetch_rss_entries(feed_url, pillar, max_items=max_items)

    if not entries:
        return {"ok": False, "error": f"No news found for '{keyword}'", "added": 0}

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)
    existing_urls, existing_titles = get_existing_records(service, spreadsheet_id)

    new_items = []
    for e in entries:
        norm_u = normalize_url(e["source_url"])
        norm_t = normalize_title(e["source_title"])
        if (norm_u not in existing_urls and e["source_url"] not in existing_urls) and (norm_t not in existing_titles):
            existing_urls.add(norm_u)
            existing_titles.add(norm_t)
            new_items.append(e)

    if not new_items:
        return {"ok": True, "message": f"Found {len(entries)} items, but all are already in queue or archive", "added": 0}

    rows_to_append = []
    for it in new_items:
        rows_to_append.append([
            it["id"],
            it["source_title"],
            it["source_url"],
            it["topic_pillar"],
            it["raw_text"],
            "",  # ai_summary
            "",  # telegram_post_text
            it["status"],
            it["quality_score"],
            it["created_at"],
            "",  # scheduled_at
            "",  # published_at
            ""   # error_log
        ])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows_to_append}
    ).execute()

    print(f"[SUCCESS] Appended {len(rows_to_append)} custom topic items for '{keyword}' to Content_Queue!\n")
    return {"ok": True, "added": len(rows_to_append), "keyword": keyword, "items": new_items}


def ingest_to_sheets(credentials_path: str, spreadsheet_id: str, max_per_feed: int = 2):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    print(f"\n[+] Connecting to Google Sheets...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    existing_urls, existing_titles = get_existing_records(service, spreadsheet_id)
    print(f"[+] Found {len(existing_urls)} existing URLs and {len(existing_titles)} titles in queue & archive.")

    sources = load_categorized_sources()
    all_new_items = []

    print(f"[+] Ingesting from {len(sources)} active content sources...")
    for src in sources:
        feed_url = src.get("url")
        pillar = src.get("pillar", "TECH_DEVELOPMENT")
        name = src.get("name", feed_url)
        print(f"  -> Fetching: {name} [{pillar}]")
        entries = fetch_rss_entries(feed_url, pillar, max_items=max_per_feed)
        
        for entry in entries:
            norm_u = normalize_url(entry["source_url"])
            norm_t = normalize_title(entry["source_title"])
            if (norm_u not in existing_urls and entry["source_url"] not in existing_urls) and (norm_t not in existing_titles):
                existing_urls.add(norm_u)
                existing_titles.add(norm_t)
                all_new_items.append(entry)

    print(f"\n[+] Identified {len(all_new_items)} new unique content items.")

    if not all_new_items:
        print("[OK] Content_Queue is already up to date.\n")
        return

    rows_to_append = []
    for it in all_new_items:
        rows_to_append.append([
            it["id"],
            it["source_title"],
            it["source_url"],
            it["topic_pillar"],
            it["raw_text"],
            "",  # ai_summary
            "",  # telegram_post_text
            it["status"],
            it["quality_score"],
            it["created_at"],
            "",  # scheduled_at
            "",  # published_at
            ""   # error_log
        ])

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows_to_append}
    ).execute()

    print(f"[SUCCESS] Appended {len(rows_to_append)} new pending items to Content_Queue in Google Sheets!\n")


def main():
    parser = argparse.ArgumentParser(description="Ingest RSS feeds into Google Sheets Content Queue")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json", help="Path to Service Account JSON key file")
    parser.add_argument("--sheet-id", "-s", default="1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE", help="Google Spreadsheet ID")
    parser.add_argument("--max-per-feed", type=int, default=2, help="Max items per feed per run")

    args = parser.parse_args()
    ingest_to_sheets(args.credentials, args.sheet_id, args.max_per_feed)


if __name__ == "__main__":
    main()


--- FILE: scripts/process_ai_content.py ---
"""
AI Content Processor with Multi-Key Rotation, Waterfall Fallback Router,
and Smart Post Formatter (Extracts clean Telegram post from AI JSON responses).
"""

import os
import sys
import json
import re
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
ENV_FILE = BASE_DIR / ".env"
CREDENTIALS_FILE = "telegram-ai-pipeline-85177bbe5835.json"
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")

# Auto-create credentials JSON from environment variable if running on Render/Cloud
if not (BASE_DIR / CREDENTIALS_FILE).exists() and os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
    with open(BASE_DIR / CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        f.write(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])

PROMPT_MAP = {
    "AI_TOOLS": "ai_tools.md",
    "AI_INDUSTRY_STARTUPS": "ai_industry_startups.md",
    "CYBERSECURITY": "cybersecurity.md",
    "LEARNING_RESOURCES": "learning_resources.md",
    "TECH_DEVELOPMENT": "technology.md",
}

PILLAR_EMOJIS = {
    "AI_TOOLS": "🛠️",
    "AI_INDUSTRY_STARTUPS": "🚀",
    "CYBERSECURITY": "🛡️",
    "LEARNING_RESOURCES": "📚",
    "TECH_DEVELOPMENT": "⚡",
}


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


def get_gemini_keys() -> list:
    keys_str = load_env_var("GEMINI_API_KEYS") or load_env_var("GEMINI_API_KEY")
    if not keys_str:
        return []
    return [k.strip() for k in keys_str.split(",") if k.strip()]


UNIVERSAL_SYSTEM_CONSTRAINT = """
CRITICAL INSTRUCTIONS FOR TELEGRAM BROADCAST:
1. Output MUST be strictly valid JSON matching the schema.
2. NEVER output literal meta words like 'Headline:', 'Heading:', '[Headline]', 'Body:', or 'Title:'.
3. Write concise, punchy, professional, and engaging text ready to be broadcast directly to Telegram.
4. Do NOT wrap output in markdown code block fences (no ```json). Output raw JSON object only.
"""


def load_prompt_template(pillar: str) -> str:
    filename = PROMPT_MAP.get(pillar, "technology.md")
    prompt_path = PROMPTS_DIR / filename
    base_prompt = ""
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            base_prompt = f.read()
    else:
        base_prompt = "You are an expert tech curator for Telegram. Summarize the following news concisely with emojis, key takeaways, and relevant hashtags."
    return f"{UNIVERSAL_SYSTEM_CONSTRAINT}\n\n{base_prompt}"


def sanitize_text(text: str) -> str:
    """Removes meta template labels, prompt artifacts, and markdown fences from post text."""
    if not text:
        return ""
    # Remove code blocks
    text = re.sub(r"^```(?:json|text|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    # Remove meta labels like "Headline:", "Heading:", "Title:", "Hook:", "Body:", "[Headline]"
    text = re.sub(r"(?i)\b(headline|heading|title)\s*:\s*", "", text)
    text = re.sub(r"(?i)\[\s*(headline|title|heading)\s*\]", "", text)
    text = re.sub(r"(?i)\b(hook|body)\s*:\s*", "", text)
    # Clean redundant blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_json_string(text: str) -> str:
    """Extracts valid JSON object from LLM string if wrapped in markdown code blocks or extra text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text


def format_to_clean_telegram_post(raw_ai_text: str, fallback_title: str, source_url: str, pillar: str) -> str:
    """
    Parses JSON output from LLM and formats it into a clean, professional,
    high-engagement Telegram message without any template artifacts or meta-labels.
    """
    emoji = PILLAR_EMOJIS.get(pillar, "⚡")
    json_candidate = clean_json_string(raw_ai_text)
    
    try:
        data = json.loads(json_candidate)
        headline = sanitize_text(data.get("headline") or fallback_title)
        hook = sanitize_text(data.get("hook", ""))
        body = sanitize_text(data.get("body", ""))
        why_it_matters = sanitize_text(data.get("why_it_matters", ""))
        key_points = data.get("key_points", [])
        hashtags = data.get("hashtags", [])

        lines = []
        # Header
        if headline:
            lines.append(f"{emoji} *{headline}*\n")
        
        # Hook / Intro
        if hook:
            lines.append(f"{hook}\n")
        
        # If body is structured text, clean it up
        if body and body != hook and body != headline:
            lines.append(f"{body}\n")
        elif why_it_matters:
            lines.append(f"*Why it matters:*\n{why_it_matters}\n")

        # Key Takeaways
        if key_points and isinstance(key_points, list):
            clean_points = [sanitize_text(p).lstrip("•-* ") for p in key_points if p and p.strip()]
            clean_points = [p for p in clean_points if p and p != headline]
            if clean_points and not any(p in body for p in clean_points[:2]):
                lines.append("*Key Takeaways:*")
                for pt in clean_points[:4]:
                    lines.append(f"• {pt}")
                lines.append("")

        # Source link
        clean_url = data.get("source_url") or source_url
        if clean_url:
            lines.append(f"🔗 [Read Full Article]({clean_url})\n")

        # Hashtags
        if hashtags and isinstance(hashtags, list):
            tag_str = " ".join([f"#{t.replace(' ', '').replace('-', '')}" for t in hashtags if t])
            if tag_str:
                lines.append(tag_str)
        elif pillar:
            lines.append(f"#{pillar.replace('_', '')} #TechNews #AI")

        formatted_post = "\n".join(lines).strip()
        return formatted_post

    except Exception:
        # If not valid JSON, clean up any code artifacts and return clean text
        clean_text = sanitize_text(raw_ai_text)
        if source_url and source_url not in clean_text:
            clean_text += f"\n\n🔗 [Read Full Article]({source_url})"
        return clean_text


def generate_with_gemini_key(api_key: str, system_prompt: str, content: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\n---\nRAW ARTICLE CONTENT:\n{content}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
    return ""


def generate_with_mistral(api_key: str, system_prompt: str, content: str) -> str:
    url = "https://api.mistral.ai/v1/chat/completions"
    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"RAW ARTICLE CONTENT:\n{content}"}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
    return ""


def generate_with_groq(api_key: str, system_prompt: str, content: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"RAW ARTICLE CONTENT:\n{content}"}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
    return ""


def generate_ai_post(system_prompt: str, content: str, title: str, url: str, pillar: str) -> tuple:
    gemini_keys = get_gemini_keys()
    mistral_key = load_env_var("MISTRAL_API_KEY")
    groq_key = load_env_var("GROQ_API_KEY")

    raw_output = ""
    provider_name = "None"

    # 1. Try Gemini Keys in order
    for idx, key in enumerate(gemini_keys, start=1):
        try:
            print(f"    [AI Router] Attempting Gemini Key #{idx} ({key[:8]}...)...")
            raw_output = generate_with_gemini_key(key, system_prompt, content)
            if raw_output:
                provider_name = f"Gemini Key #{idx}"
                break
        except Exception as e:
            print(f"    [AI Router] Gemini Key #{idx} failed / rate-limited: {e}")

    # 2. Fallback to Mistral AI
    if not raw_output and mistral_key:
        try:
            print(f"    [AI Router] ⚠️ All Gemini keys exhausted. Falling back to Mistral AI...")
            raw_output = generate_with_mistral(mistral_key, system_prompt, content)
            if raw_output:
                provider_name = "Mistral AI"
        except Exception as e:
            print(f"    [AI Router] Mistral fallback failed: {e}")

    # 3. Fallback to Groq Cloud
    if not raw_output and groq_key:
        try:
            print(f"    [AI Router] ⚠️ Mistral failed. Falling back to Groq Llama-3.3...")
            raw_output = generate_with_groq(groq_key, system_prompt, content)
            if raw_output:
                provider_name = "Groq Cloud"
        except Exception as e:
            print(f"    [AI Router] Groq fallback failed: {e}")

    if not raw_output:
        return "", "None"

    # Format into beautiful clean Telegram post
    formatted_post = format_to_clean_telegram_post(raw_output, title, url, pillar)
    return formatted_post, provider_name


def process_queue(credentials_path: str, spreadsheet_id: str, limit: int = 10):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_file_path = BASE_DIR / credentials_path
    if not creds_file_path.exists():
        print(f"[!] Credentials file not found: {creds_file_path}")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        str(creds_file_path), scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    print(f"\n[+] Scanning Content_Queue for PENDING items...")
    res = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A2:M"
    ).execute()
    rows = res.get("values", [])

    if not rows:
        print("[OK] No rows found in Content_Queue.")
        return

    processed_count = 0
    for idx, row in enumerate(rows, start=2):
        if processed_count >= limit:
            break

        # Schema: id(0), source_title(1), source_url(2), topic_pillar(3), raw_text(4), ai_summary(5), telegram_post_text(6), status(7)
        status = row[7] if len(row) > 7 else ""
        if status == "PENDING":
            title = row[1] if len(row) > 1 else ""
            url = row[2] if len(row) > 2 else ""
            pillar = row[3] if len(row) > 3 else "TECH_DEVELOPMENT"
            raw_text = row[4] if len(row) > 4 else title

            print(f"\n[+] Processing item {processed_count + 1}: \"{title[:60]}\" [{pillar}]")
            prompt_template = load_prompt_template(pillar)
            combined_content = f"Title: {title}\nURL: {url}\nSummary/Context: {raw_text}"
            
            ai_post, provider = generate_ai_post(prompt_template, combined_content, title, url, pillar)
            if ai_post:
                # Update status to APPROVED, ai_summary, telegram_post_text
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'Content_Queue'!F{idx}:H{idx}",
                    valueInputOption="USER_ENTERED",
                    body={
                        "values": [[raw_text[:250], ai_post, "APPROVED"]]
                    }
                ).execute()
                print(f"  [OK] Generated clean post using {provider}! Updated row {idx} to APPROVED.")
                processed_count += 1
            else:
                print(f"  [!] Failed generating AI post for row {idx} across all providers.")

    print(f"\n[SUCCESS] Successfully formatted {processed_count} items with AI!\n")


def reformat_existing_approved_rows(credentials_path: str, spreadsheet_id: str):
    """Re-formats any existing rows in Content_Queue that still have raw JSON in telegram_post_text."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_file_path = BASE_DIR / credentials_path
    if not creds_file_path.exists():
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        str(creds_file_path), scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    res = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A2:M"
    ).execute()
    rows = res.get("values", [])

    updated = 0
    for idx, row in enumerate(rows, start=2):
        post_text = row[6] if len(row) > 6 else ""
        if post_text and ('"headline":' in post_text or '"hook":' in post_text or post_text.strip().startswith("{")):
            title = row[1] if len(row) > 1 else ""
            url = row[2] if len(row) > 2 else ""
            pillar = row[3] if len(row) > 3 else "TECH_DEVELOPMENT"
            
            clean_post = format_to_clean_telegram_post(post_text, title, url, pillar)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'Content_Queue'!G{idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [[clean_post]]}
            ).execute()
            updated += 1

    if updated:
        print(f"[SUCCESS] Cleaned and reformatted {updated} existing raw JSON posts in Google Sheets!")


def main():
    parser = argparse.ArgumentParser(description="Process pending items with AI waterfall router")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json")
    parser.add_argument("--sheet-id", "-s", default="1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--reformat-existing", action="store_true", help="Reformat existing JSON rows")

    args = parser.parse_args()
    
    # Always clean any existing raw JSON rows first
    reformat_existing_approved_rows(args.credentials, args.sheet_id)
    process_queue(args.credentials, args.sheet_id, args.limit)


if __name__ == "__main__":
    main()


--- FILE: scripts/publish_telegram.py ---
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


def publish_approved_content(credentials_path: str, spreadsheet_id: str, limit: int = 1, prune_published: bool = False):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

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
    rows_to_delete_indices = []

    for idx, row in enumerate(rows, start=2):
        if published_count >= limit:
            break

        # Schema: id(0), source_title(1), source_url(2), topic_pillar(3), raw_text(4), ai_summary(5), telegram_post_text(6), status(7)
        status = row[7] if len(row) > 7 else ""
        if status == "APPROVED":
            post_id = row[0] if len(row) > 0 else ""
            title = row[1] if len(row) > 1 else ""
            source_url = row[2] if len(row) > 2 else ""
            pillar = row[3] if len(row) > 3 else ""
            post_text = row[6] if len(row) > 6 else ""

            if not post_text:
                continue

            # Safety check: Clean and reformat if post_text contains raw JSON
            from process_ai_content import format_to_clean_telegram_post
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


--- FILE: scripts/init_sheets.py ---
"""
Google Sheets Initializer for Telegram AI Content Pipeline.

Initializes the required 4 tabs, column headers, styling, and default topic pillars
either directly via Google Sheets API (using Service Account JSON) or by generating
ready-to-import CSV files.

Usage:
    # 1. Direct API Initialization:
    python scripts/init_sheets.py --credentials path/to/service-account.json --sheet-id YOUR_SPREADSHEET_ID

    # 2. Generate CSVs for manual 1-click Import:
    python scripts/init_sheets.py --export-csv
"""

import os
import sys
import json
import csv
import argparse
from pathlib import Path

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "config" / "sheets_schema.json"


def load_schema() -> dict:
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_FILE}")
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def export_csv_templates(schema: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[+] Exporting CSV templates to: {output_dir}")

    for tab_name, tab_data in schema.get("tabs", {}).items():
        csv_path = output_dir / f"{tab_name}.csv"
        headers = tab_data.get("headers", [])
        default_data = tab_data.get("default_data", [])

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in default_data:
                writer.writerow(row)

        print(f"  -> Created {csv_path.name} ({len(headers)} columns)")

    print("\n[OK] CSV templates generated! You can import them directly into Google Sheets:")
    print("     Open Google Sheets -> File -> Import -> Upload -> Select CSV -> Insert new sheet(s).\n")


def init_via_google_api(credentials_path: str, spreadsheet_id: str, schema: dict):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("\n[!] Google API libraries not installed. Install them with:")
        print("    pip install google-api-python-client google-auth")
        print("\nOr run with --export-csv to generate ready-to-import CSV files instead.")
        sys.exit(1)

    if not os.path.exists(credentials_path):
        print(f"[!] Error: Credentials file not found at: {credentials_path}")
        sys.exit(1)

    print(f"\n[+] Authenticating with Google Cloud Service Account...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    # 1. Fetch current spreadsheet info
    print(f"[+] Connecting to Spreadsheet ID: {spreadsheet_id}")
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in spreadsheet.get("sheets", [])}

    requests = []

    # 2. Ensure each tab exists
    for tab_name in schema.get("tabs", {}).keys():
        if tab_name not in existing_sheets:
            print(f"  -> Creating tab: {tab_name}")
            requests.append({
                "addSheet": {
                    "properties": {
                        "title": tab_name,
                        "gridProperties": {
                            "frozenRowCount": 1
                        }
                    }
                }
            })
        else:
            print(f"  -> Tab already exists: {tab_name} (freezing top row)")
            requests.append({
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": existing_sheets[tab_name],
                        "gridProperties": {
                            "frozenRowCount": 1
                        }
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()

    # 3. Refresh sheet IDs after creation
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id_map = {s["properties"]["title"]: s["properties"]["sheetId"] for s in spreadsheet.get("sheets", [])}

    # 4. Populate Headers and Default Data
    value_updates = []
    format_requests = []

    for tab_name, tab_data in schema.get("tabs", {}).items():
        headers = tab_data.get("headers", [])
        default_data = tab_data.get("default_data", [])
        sheet_id = sheet_id_map[tab_name]

        rows = [headers] + default_data
        value_updates.append({
            "range": f"'{tab_name}'!A1",
            "values": rows
        })

        # Style header row (Bold + Dark Slate Background + White Text)
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(headers)
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.15, "green": 0.18, "blue": 0.25},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        })

    # Execute Value updates
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": value_updates
        }
    ).execute()

    # Execute Formatting updates
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": format_requests}
    ).execute()

    print("\n[SUCCESS] Google Sheet initialized successfully with 4 styled tabs and default topic pillars!")


def main():
    parser = argparse.ArgumentParser(description="Initialize Google Sheets for Telegram AI Pipeline")
    parser.add_argument("--credentials", "-c", help="Path to Service Account JSON key file")
    parser.add_argument("--sheet-id", "-s", help="Google Spreadsheet ID")
    parser.add_argument("--export-csv", action="store_true", help="Export CSV templates for manual import")
    parser.add_argument("--output-dir", default="./sheets_templates", help="Output directory for CSVs")

    args = parser.parse_args()
    schema = load_schema()

    if args.export_csv or not (args.credentials and args.sheet_id):
        export_csv_templates(schema, Path(args.output_dir))
        return

    init_via_google_api(args.credentials, args.sheet_id, schema)


if __name__ == "__main__":
    main()


--- FILE: dashboard/index.html ---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Telegram AI Pipeline - Mission Control & Topic Ingest</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #07090e;
      --bg-surface: #0e141f;
      --bg-card: rgba(18, 26, 41, 0.75);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-highlight: rgba(0, 242, 254, 0.35);
      
      --accent-cyan: #00f2fe;
      --accent-blue: #4facfe;
      --accent-purple: #8b5cf6;
      --accent-emerald: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Plus Jakarta Sans', sans-serif;
    }

    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      background-image: 
        radial-gradient(circle at 10% 10%, rgba(0, 242, 254, 0.04) 0%, transparent 40%),
        radial-gradient(circle at 90% 90%, rgba(139, 92, 246, 0.04) 0%, transparent 40%);
    }

    /* Top Navigation */
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 1rem 2rem;
      border-bottom: 1px solid var(--border-color);
      background: rgba(7, 9, 14, 0.85);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .logo-icon {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.2rem;
      font-weight: 800;
      color: #030712;
      box-shadow: 0 0 20px rgba(0, 242, 254, 0.3);
    }

    .brand h1 {
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(to right, #fff, #94a3b8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .header-links {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .badge-channel, .badge-sheet {
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.4rem 0.85rem;
      border-radius: 9999px;
      text-decoration: none;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.2s;
    }

    .badge-channel {
      background: rgba(0, 242, 254, 0.1);
      color: var(--accent-cyan);
      border: 1px solid rgba(0, 242, 254, 0.25);
    }
    .badge-channel:hover {
      background: rgba(0, 242, 254, 0.2);
    }

    .badge-sheet {
      background: rgba(16, 185, 129, 0.1);
      color: var(--accent-emerald);
      border: 1px solid rgba(16, 185, 129, 0.25);
    }
    .badge-sheet:hover {
      background: rgba(16, 185, 129, 0.2);
    }

    /* Main Container */
    main {
      flex: 1;
      padding: 1.5rem 2rem;
      max-width: 1600px;
      margin: 0 auto;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }

    /* Stats Grid */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
    }

    .stat-card {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      position: relative;
      overflow: hidden;
    }

    .stat-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 600;
    }

    .stat-value {
      font-size: 1.75rem;
      font-weight: 800;
      letter-spacing: -0.03em;
    }

    .stat-badge {
      font-size: 0.7rem;
      padding: 0.15rem 0.5rem;
      border-radius: 6px;
      font-weight: 700;
    }
    .badge-amber { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
    .badge-emerald { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-blue { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
    .badge-purple { background: rgba(139, 92, 246, 0.15); color: #c084fc; }

    /* Topic Ingestion Toolbar */
    .topic-search-card {
      background: linear-gradient(135deg, rgba(0, 242, 254, 0.06), rgba(139, 92, 246, 0.06));
      border: 1px solid var(--border-highlight);
      border-radius: 14px;
      padding: 1rem 1.25rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      justify-content: space-between;
    }

    .topic-search-inputs {
      display: flex;
      flex-wrap: wrap;
      gap: 0.6rem;
      align-items: center;
      flex: 1;
    }

    .search-input {
      background: #090d14;
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: var(--text-main);
      padding: 0.55rem 0.9rem;
      border-radius: 8px;
      font-size: 0.85rem;
      outline: none;
      min-width: 260px;
      flex: 1;
      transition: all 0.2s;
    }
    .search-input:focus {
      border-color: var(--accent-cyan);
      box-shadow: 0 0 10px rgba(0, 242, 254, 0.2);
    }

    /* Controls & Auto-Pilot Row */
    .control-row {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 1.25rem;
    }

    @media (max-width: 900px) {
      .control-row { grid-template-columns: 1fr; }
    }

    .action-panel {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 1.1rem 1.25rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 0.75rem;
    }

    .action-group {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .btn {
      padding: 0.5rem 1rem;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      border: none;
      transition: all 0.2s;
    }

    .btn-primary {
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
      color: #030712;
      box-shadow: 0 4px 15px rgba(0, 242, 254, 0.25);
    }
    .btn-primary:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(0, 242, 254, 0.4);
    }

    .btn-secondary {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-color);
      color: var(--text-main);
    }
    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.2);
    }

    .btn-success {
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
    }
    .btn-success:hover {
      background: rgba(16, 185, 129, 0.35);
    }

    .btn-danger {
      background: rgba(244, 63, 94, 0.15);
      border: 1px solid rgba(244, 63, 94, 0.3);
      color: #fb7185;
    }
    .btn-danger:hover {
      background: rgba(244, 63, 94, 0.25);
    }

    /* Auto-Pilot Card */
    .autopilot-card {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 1.1rem 1.25rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 0.75rem;
    }

    .toggle-wrapper {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .switch {
      position: relative;
      display: inline-block;
      width: 46px;
      height: 24px;
    }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider {
      position: absolute;
      cursor: pointer;
      inset: 0;
      background-color: #334155;
      transition: .3s;
      border-radius: 34px;
    }
    .slider:before {
      position: absolute;
      content: "";
      height: 18px;
      width: 18px;
      left: 3px;
      bottom: 3px;
      background-color: white;
      transition: .3s;
      border-radius: 50%;
    }
    input:checked + .slider {
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-emerald));
    }
    input:checked + .slider:before {
      transform: translateX(22px);
    }

    /* Content Split Area */
    .content-section {
      display: grid;
      grid-template-columns: 2.3fr 1fr;
      gap: 1.25rem;
    }

    @media (max-width: 1100px) {
      .content-section { grid-template-columns: 1fr; }
    }

    .panel {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      max-height: 720px;
    }

    .panel-header-controls {
      display: flex;
      flex-direction: column;
      gap: 0.6rem;
    }

    .search-filter-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
      justify-content: space-between;
    }

    .table-search-box {
      background: #0b0f17;
      border: 1px solid rgba(255, 255, 255, 0.15);
      color: var(--text-main);
      padding: 0.45rem 0.8rem;
      border-radius: 8px;
      font-size: 0.8rem;
      outline: none;
      min-width: 220px;
      flex: 1;
    }
    .table-search-box:focus {
      border-color: var(--accent-cyan);
    }

    .filter-select {
      background: #182232;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 0.45rem 0.8rem;
      border-radius: 8px;
      font-size: 0.8rem;
      outline: none;
      cursor: pointer;
    }

    .filter-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
    }
    .filter-pill {
      font-size: 0.72rem;
      padding: 0.25rem 0.65rem;
      border-radius: 20px;
      background: #141c2b;
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.2s;
    }
    .filter-pill:hover, .filter-pill.active {
      background: var(--accent-cyan);
      color: #030712;
      font-weight: 700;
      border-color: var(--accent-cyan);
    }

    .status-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
    }
    .status-filter-pill {
      font-size: 0.72rem;
      padding: 0.25rem 0.65rem;
      border-radius: 20px;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.2s;
    }
    .status-filter-pill:hover, .status-filter-pill.active {
      background: var(--accent-purple);
      color: #ffffff;
      font-weight: 700;
      border-color: var(--accent-purple);
    }

    .table-container {
      overflow-y: auto;
      border-radius: 8px;
      flex: 1;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.8rem;
    }

    th {
      background: rgba(14, 20, 31, 0.95);
      color: var(--text-muted);
      padding: 0.65rem 0.75rem;
      font-weight: 600;
      position: sticky;
      top: 0;
      z-index: 10;
    }

    td {
      padding: 0.65rem 0.75rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-main);
      vertical-align: middle;
    }

    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }

    .img-thumb-wrap {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: 6px;
      background: #182232;
      overflow: hidden;
      margin-right: 0.5rem;
      flex-shrink: 0;
    }
    .img-thumb {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.2s;
    }
    .img-thumb:hover {
      transform: scale(1.4);
    }

    .pillar-tag {
      font-size: 0.68rem;
      font-weight: 600;
      padding: 0.2rem 0.4rem;
      border-radius: 6px;
      background: rgba(148, 163, 184, 0.1);
      color: var(--text-muted);
    }

    .status-pill {
      font-size: 0.68rem;
      font-weight: 700;
      padding: 0.2rem 0.5rem;
      border-radius: 9999px;
      display: inline-block;
    }
    .status-PENDING { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
    .status-APPROVED { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .status-PUBLISHED { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
    .status-REJECTED { background: rgba(244, 63, 94, 0.2); color: #f43f5e; }

    .btn-row {
      padding: 0.22rem 0.45rem;
      font-size: 0.7rem;
      border-radius: 5px;
    }

    /* Live Terminal Console */
    .terminal {
      background: #06090e;
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 0.8rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      color: #38bdf8;
      overflow-y: auto;
      flex: 1;
      min-height: 250px;
      max-height: 600px;
      line-height: 1.45;
    }
    .terminal-line {
      white-space: pre-wrap;
      word-break: break-word;
      margin-bottom: 0.2rem;
    }

    /* Batch Selection Toolbar */
    .batch-bar {
      display: none;
      align-items: center;
      justify-content: space-between;
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 0.5rem 1rem;
      border-radius: 8px;
    }
    .batch-bar.active {
      display: flex;
    }

    /* Modal for Post Editing & Preview */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.8);
      backdrop-filter: blur(8px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s;
    }
    .modal-backdrop.open {
      opacity: 1;
      pointer-events: auto;
    }

    .modal-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      max-width: 760px;
      width: 94%;
      max-height: 90vh;
      overflow-y: auto;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    }

    .referral-helper-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      background: rgba(0, 242, 254, 0.05);
      border: 1px solid rgba(0, 242, 254, 0.2);
      border-radius: 10px;
      padding: 0.6rem 0.8rem;
      align-items: center;
    }

    .ref-input {
      flex: 1;
      min-width: 200px;
      background: #0b0f17;
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #fff;
      padding: 0.35rem 0.6rem;
      border-radius: 6px;
      font-size: 0.8rem;
    }

    .modal-img-preview-box {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      background: rgba(255, 255, 255, 0.03);
      border: 1px dashed var(--border-color);
      padding: 0.6rem;
      border-radius: 8px;
    }
    .modal-img-preview {
      width: 60px;
      height: 60px;
      border-radius: 6px;
      object-fit: cover;
      background: #182232;
    }

    .edit-textarea {
      width: 100%;
      height: 240px;
      background: #0b0f17;
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 10px;
      color: #f8fafc;
      padding: 0.9rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      line-height: 1.5;
      resize: vertical;
      outline: none;
    }
    .edit-textarea:focus {
      border-color: var(--accent-cyan);
    }

    .modal-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
    }

    /* Toast Notification */
    .toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: #0f172a;
      border: 1px solid var(--accent-cyan);
      color: #fff;
      padding: 0.75rem 1.25rem;
      border-radius: 10px;
      font-size: 0.85rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
      z-index: 200;
      opacity: 0;
      transform: translateY(10px);
      transition: all 0.3s ease;
      pointer-events: none;
    }
    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="logo-icon">⚡</div>
      <div>
        <h1>Telegram AI Pipeline</h1>
      </div>
    </div>

    <div class="header-links">
      <a href="https://t.me/maazzalii" target="_blank" class="badge-channel">
        ✈️ @maazzalii
      </a>
      <a href="https://docs.google.com/spreadsheets/d/1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE/edit" target="_blank" class="badge-sheet">
        📊 Google Sheet
      </a>
    </div>
  </header>

  <main>

    <!-- Top KPI Cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-header">
          <span>Pending Articles</span>
          <span class="stat-badge badge-amber">Awaiting AI/Review</span>
        </div>
        <div class="stat-value" id="val-pending">0</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <span>Approved Posts</span>
          <span class="stat-badge badge-emerald">Ready to Broadcast</span>
        </div>
        <div class="stat-value" id="val-approved">0</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <span>Published Live</span>
          <span class="stat-badge badge-blue">In Telegram Channel</span>
        </div>
        <div class="stat-value" id="val-published">0</div>
      </div>

      <div class="stat-card">
        <div class="stat-header">
          <span>AI Multi-Failover</span>
          <span class="stat-badge badge-purple">Active</span>
        </div>
        <div class="stat-value" style="font-size: 1.05rem; font-weight: 700; margin-top: 0.3rem;">
          Gemini (x5) ➔ Mistral ➔ Groq
        </div>
      </div>
    </div>

    <!-- On-Demand Topic & Keyword Search Ingest -->
    <div class="topic-search-card">
      <div class="topic-search-inputs">
        <span style="font-size: 0.85rem; font-weight: 700; color: var(--accent-cyan); display: flex; align-items: center; gap: 0.3rem;">
          🎯 Live Topic News Ingest:
        </span>
        <input 
          type="text" 
          id="topic-keyword-input" 
          class="search-input" 
          placeholder="Enter search term or keyword (e.g. Claude 3.7, DeepSeek, Cybersecurity, Cursor AI)..." 
          onkeydown="if(event.key === 'Enter') fetchTopicNews()"
        />
        <select id="topic-pillar-select" class="filter-select">
          <option value="AI_INDUSTRY_STARTUPS">🚀 AI News & Startups</option>
          <option value="AI_TOOLS">🛠️ AI Tools (Referrals)</option>
          <option value="LEARNING_RESOURCES">💡 Prompts & Tutorials</option>
          <option value="CYBERSECURITY">🛡️ Cyber Security</option>
          <option value="TECH_DEVELOPMENT">⚡ Tech Development</option>
        </select>
        <select id="topic-count-select" class="filter-select" style="width: 85px;">
          <option value="3">3 posts</option>
          <option value="5" selected>5 posts</option>
          <option value="8">8 posts</option>
        </select>
        <button class="btn btn-primary" id="btn-fetch-topic" onclick="fetchTopicNews()">
          🔍 Ingest Topic News
        </button>
      </div>
    </div>

    <!-- Controls & Auto-Pilot Row -->
    <div class="control-row">
      <!-- 1-Click Action Toolbar -->
      <div class="action-panel">
        <div style="font-size: 0.85rem; font-weight: 700; color: var(--text-muted);">⚡ MANUAL PIPELINE CONTROLS</div>
        <div class="action-group">
          <button class="btn btn-primary" onclick="triggerAction('all')">
            🚀 Run Full Cycle
          </button>
          <button class="btn btn-secondary" onclick="triggerAction('ingest')">
            📥 Ingest Standard Feeds
          </button>
          <button class="btn btn-secondary" onclick="triggerAction('process-ai')">
            🧠 AI Auto-Format
          </button>
          <button class="btn btn-secondary" onclick="triggerAction('publish')">
            📢 Publish Next Approved
          </button>
          <button class="btn btn-danger" onclick="triggerAction('clear-queue')">
            🧹 Clear Queue
          </button>
        </div>
      </div>

      <!-- Auto-Pilot Scheduler Card -->
      <div class="autopilot-card">
        <div class="toggle-wrapper">
          <div>
            <div style="font-size: 0.85rem; font-weight: 700;">⏰ AUTO-PILOT SCHEDULER</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);" id="autopilot-status-text">Auto-posts 2-3 times/day</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="autopilot-toggle" onchange="toggleAutopilot()">
            <span class="slider"></span>
          </label>
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--text-muted);">Frequency:</span>
          <select id="autopilot-freq" class="filter-select" onchange="toggleAutopilot()">
            <option value="4">Every 4 Hours (6 posts/day)</option>
            <option value="6">Every 6 Hours (4 posts/day)</option>
            <option value="8" selected>Every 8 Hours (3 posts/day)</option>
            <option value="12">Every 12 Hours (2 posts/day)</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Main Content Split -->
    <div class="content-section">
      <!-- Live Content Queue Table -->
      <div class="panel">
        <div class="panel-header-controls">
          <div class="search-filter-row">
            <input 
              type="text" 
              id="queue-search-filter" 
              class="table-search-box" 
              placeholder="🔍 Search Queue (Title, topic, ID, content...)" 
              oninput="renderQueueTable()"
            />
            <div class="status-pills" id="status-pills-bar">
              <button class="status-filter-pill active" onclick="setStatusFilter('ALL')">All Status</button>
              <button class="status-filter-pill" onclick="setStatusFilter('PENDING')">⏳ Pending</button>
              <button class="status-filter-pill" onclick="setStatusFilter('APPROVED')">✅ Approved</button>
              <button class="status-filter-pill" onclick="setStatusFilter('PUBLISHED')">🚀 Published</button>
              <button class="status-filter-pill" onclick="setStatusFilter('REJECTED')">❌ Rejected</button>
            </div>
          </div>

          <div class="filter-pills" id="filter-pills-bar">
            <button class="filter-pill active" onclick="setCategoryFilter('ALL')">🌟 All Categories</button>
            <button class="filter-pill" onclick="setCategoryFilter('AI_TOOLS')">🛠️ AI Tools</button>
            <button class="filter-pill" onclick="setCategoryFilter('LEARNING_RESOURCES')">💡 Prompts & Guides</button>
            <button class="filter-pill" onclick="setCategoryFilter('AI_INDUSTRY_STARTUPS')">🚀 AI Startups</button>
            <button class="filter-pill" onclick="setCategoryFilter('CYBERSECURITY')">🛡️ Cyber Security</button>
            <button class="filter-pill" onclick="setCategoryFilter('TECH_DEVELOPMENT')">⚡ Tech Dev</button>
          </div>
        </div>

        <!-- Multi-Select Batch Action Bar -->
        <div class="batch-bar" id="batch-action-bar">
          <span id="batch-count-text" style="font-size: 0.8rem; font-weight: 600; color: var(--accent-cyan);">0 items selected</span>
          <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
            <button class="btn btn-success btn-row" onclick="batchSetStatus('APPROVED')">✅ Approve Selected</button>
            <button class="btn btn-danger btn-row" onclick="batchSetStatus('REJECTED')">❌ Reject Selected</button>
            <button class="btn btn-primary btn-row" onclick="publishBatchSelected()">📢 Publish Selected</button>
            <button class="btn btn-secondary btn-row" onclick="clearAllSelections()">Cancel</button>
          </div>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th style="width: 28px;"><input type="checkbox" id="select-all-cb" onchange="toggleSelectAll(this.checked)"></th>
                <th>Article / Post Content</th>
                <th>Category</th>
                <th>Status</th>
                <th style="text-align: right;">Action Controls</th>
              </tr>
            </thead>
            <tbody id="queue-tbody">
              <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">Loading sheet items...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Realtime Execution Terminal -->
      <div class="panel">
        <div class="panel-header-controls" style="flex-direction: row; justify-content: space-between; align-items: center;">
          <span style="font-weight: 700; font-size: 0.95rem;">Live Console Output</span>
          <span id="log-status" style="font-size: 0.75rem; color: var(--accent-emerald);">● Online</span>
        </div>
        <div class="terminal" id="terminal-console">
          <div class="terminal-line">> System initialized. Ready.</div>
        </div>
      </div>
    </div>

  </main>

  <!-- Post Editor & Referral Link Modal -->
  <div class="modal-backdrop" id="edit-modal" onclick="closeModal(event)">
    <div class="modal-card" onclick="event.stopPropagation()">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2 style="font-size: 1.1rem; font-weight: 700;">✏️ Edit Post & Media</h2>
        <span id="modal-row-tag" class="pillar-tag">Row #</span>
      </div>

      <!-- Image URL & Preview Bar -->
      <div class="modal-img-preview-box">
        <img id="modal-img-preview" class="modal-img-preview" src="" alt="Thumbnail" style="display: none;" />
        <div style="flex: 1; display: flex; flex-direction: column; gap: 0.3rem;">
          <span style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted);">📸 Post Image / Photo URL (Optional):</span>
          <div style="display: flex; gap: 0.4rem;">
            <input type="url" id="modal-img-input" class="ref-input" placeholder="https://example.com/image.jpg..." oninput="updateModalImagePreview()" />
            <button class="btn btn-secondary btn-row" onclick="updateModalImagePreview()">👁️ Preview</button>
          </div>
        </div>
      </div>

      <!-- Referral Link Insertion Bar -->
      <div class="referral-helper-bar">
        <span style="font-size: 0.75rem; font-weight: 700; color: var(--accent-cyan);">🔗 Referral Link:</span>
        <input type="url" id="ref-link-input" class="ref-input" placeholder="https://youraffiliatelink.com/ref?code=..." />
        <button class="btn btn-secondary btn-row" onclick="insertReferralLink()">➕ Insert Link</button>
        <button class="btn btn-secondary btn-row" onclick="insertPromptGuideTemplate()">💡 Add Prompt Box</button>
      </div>

      <textarea id="modal-edit-text" class="edit-textarea" placeholder="Post text will load here..."></textarea>

      <div class="modal-actions">
        <div style="display: flex; gap: 0.4rem;">
          <button class="btn btn-danger btn-row" onclick="setPostStatusFromModal('REJECTED')">❌ Reject Post</button>
          <button class="btn btn-success btn-row" onclick="setPostStatusFromModal('APPROVED')">✅ Mark Approved</button>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
          <button class="btn btn-secondary" onclick="savePostChanges()">💾 Save Changes</button>
          <button class="btn btn-primary" id="modal-publish-btn" onclick="publishCurrentModalPost()">🚀 Publish Now</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Toast Element -->
  <div id="toast-notify" class="toast">
    <span id="toast-icon">⚡</span>
    <span id="toast-msg">Notification message</span>
  </div>

  <script>
    let queueItems = [];
    let currentEditingRow = null;
    let selectedRowIndices = new Set();
    let currentCategoryFilter = 'ALL';
    let currentStatusFilter = 'ALL';

    function showToast(msg, isSuccess = true) {
      const toast = document.getElementById('toast-notify');
      const toastMsg = document.getElementById('toast-msg');
      const toastIcon = document.getElementById('toast-icon');
      toastMsg.innerText = msg;
      toastIcon.innerText = isSuccess ? '✅' : '⚠️';
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 3500);
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        document.getElementById('val-pending').innerText = data.pending || 0;
        document.getElementById('val-approved').innerText = data.approved || 0;
        document.getElementById('val-published').innerText = data.published || 0;

        if (data.autopilot) {
          document.getElementById('autopilot-toggle').checked = !!data.autopilot.enabled;
          document.getElementById('autopilot-status-text').innerText = data.autopilot.enabled 
            ? `🟢 Auto-Pilot Active (Every ${data.autopilot.interval_hours}h)` 
            : '⚪ Auto-Pilot Paused';
        }

        queueItems = data.items || [];
        renderQueueTable();
      } catch (e) {
        console.error("Failed fetching status", e);
      }
    }

    async function fetchLogs() {
      try {
        const res = await fetch('/api/logs');
        const data = await res.json();
        const terminal = document.getElementById('terminal-console');
        
        terminal.innerHTML = (data.logs || []).map(l => `<div class="terminal-line">${escapeHtml(l)}</div>`).join('');
        terminal.scrollTop = terminal.scrollHeight;
      } catch (e) {
        console.error("Failed fetching logs", e);
      }
    }

    function setCategoryFilter(pillar) {
      currentCategoryFilter = pillar;
      document.querySelectorAll('#filter-pills-bar .filter-pill').forEach(p => p.classList.remove('active'));
      event.target.classList.add('active');
      renderQueueTable();
    }

    function setStatusFilter(status) {
      currentStatusFilter = status;
      document.querySelectorAll('#status-pills-bar .status-filter-pill').forEach(p => p.classList.remove('active'));
      event.target.classList.add('active');
      renderQueueTable();
    }

    async function fetchTopicNews() {
      const input = document.getElementById('topic-keyword-input');
      const keyword = input.value.trim();
      if (!keyword) {
        alert("Please enter a topic keyword or search term (e.g. 'Claude 3.7', 'DeepSeek', 'Cybersecurity').");
        return;
      }

      const pillar = document.getElementById('topic-pillar-select').value;
      const count = document.getElementById('topic-count-select').value;
      const btn = document.getElementById('btn-fetch-topic');

      btn.disabled = true;
      btn.innerText = "⏳ Ingesting...";
      showToast(`Searching live news for '${keyword}'...`);

      try {
        const res = await fetch('/api/fetch-topic', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ keyword, pillar, max_items: parseInt(count) })
        });
        const data = await res.json();
        if (data.ok) {
          showToast(`Added ${data.added || 0} news articles for '${keyword}' to queue!`);
          input.value = '';
          fetchStatus();
        } else {
          alert("Error fetching topic news: " + (data.error || "Unknown error"));
        }
      } catch (e) {
        alert("Network error: " + e);
      } finally {
        btn.disabled = false;
        btn.innerText = "🔍 Ingest Topic News";
      }
    }

    async function setRowStatus(rowIndex, newStatus) {
      showToast(`Setting row #${rowIndex} to ${newStatus}...`);
      try {
        const res = await fetch('/api/set-status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ row_index: rowIndex, status: newStatus })
        });
        const data = await res.json();
        if (data.ok) {
          showToast(`Row #${rowIndex} marked as ${newStatus}!`);
          fetchStatus();
        }
      } catch (e) {
        alert("Failed to update status: " + e);
      }
    }

    async function batchSetStatus(newStatus) {
      const indices = Array.from(selectedRowIndices);
      if (indices.length === 0) return;

      showToast(`Updating ${indices.length} post(s) to ${newStatus}...`);
      for (const rIdx of indices) {
        await fetch('/api/set-status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ row_index: rIdx, status: newStatus })
        });
      }
      clearAllSelections();
      showToast(`Batch status update completed!`);
      fetchStatus();
    }

    function renderQueueTable() {
      const tbody = document.getElementById('queue-tbody');
      const searchQuery = (document.getElementById('queue-search-filter').value || '').toLowerCase().trim();

      const filtered = queueItems.filter(it => {
        // Category filter
        if (currentCategoryFilter !== 'ALL' && it.topic_pillar !== currentCategoryFilter) {
          return false;
        }
        // Status filter
        if (currentStatusFilter !== 'ALL' && it.status !== currentStatusFilter) {
          return false;
        }
        // Search filter
        if (searchQuery) {
          const matchTitle = (it.source_title || '').toLowerCase().includes(searchQuery);
          const matchText = (it.telegram_post_text || '').toLowerCase().includes(searchQuery);
          const matchUrl = (it.source_url || '').toLowerCase().includes(searchQuery);
          const matchPillar = (it.topic_pillar || '').toLowerCase().includes(searchQuery);
          const matchId = (it.id || '').toLowerCase().includes(searchQuery);
          if (!matchTitle && !matchText && !matchUrl && !matchPillar && !matchId) {
            return false;
          }
        }
        return true;
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">No items matching the selected filters.</td></tr>`;
        return;
      }

      tbody.innerHTML = filtered.map(it => {
        const isChecked = selectedRowIndices.has(it.row_index);
        const hasImg = it.image_url && it.image_url.startsWith('http');
        const imgHtml = hasImg 
          ? `<div class="img-thumb-wrap" title="Attached Image"><img src="${escapeHtml(it.image_url)}" class="img-thumb" onerror="this.style.display='none'" /></div>`
          : `<div class="img-thumb-wrap" style="color: var(--text-dim); font-size: 0.8rem;">📄</div>`;

        // Render Action buttons based on status
        let actionButtons = '';
        if (it.status === 'PENDING') {
          actionButtons = `
            <button class="btn btn-success btn-row" onclick="setRowStatus(${it.row_index}, 'APPROVED')" title="Approve this post">✅ Approve</button>
            <button class="btn btn-danger btn-row" onclick="setRowStatus(${it.row_index}, 'REJECTED')" title="Reject this post">❌ Reject</button>
            <button class="btn btn-secondary btn-row" onclick="openEditModal(${it.row_index})">✏️ Edit</button>
            <button class="btn btn-primary btn-row" id="btn-post-${it.row_index}" onclick="publishSingle(${it.row_index})">📢 Post</button>
          `;
        } else if (it.status === 'APPROVED') {
          actionButtons = `
            <button class="btn btn-primary btn-row" id="btn-post-${it.row_index}" onclick="publishSingle(${it.row_index})">🚀 Post Now</button>
            <button class="btn btn-secondary btn-row" onclick="openEditModal(${it.row_index})">✏️ Edit</button>
            <button class="btn btn-danger btn-row" onclick="setRowStatus(${it.row_index}, 'REJECTED')">❌ Reject</button>
          `;
        } else if (it.status === 'REJECTED') {
          actionButtons = `
            <button class="btn btn-secondary btn-row" onclick="setRowStatus(${it.row_index}, 'APPROVED')">🔄 Restore / Approve</button>
            <button class="btn btn-secondary btn-row" onclick="openEditModal(${it.row_index})">✏️ Edit</button>
          `;
        } else { // PUBLISHED
          actionButtons = `
            <button class="btn btn-secondary btn-row" onclick="openEditModal(${it.row_index})">✏️ View / Edit</button>
            <button class="btn btn-secondary btn-row" id="btn-post-${it.row_index}" onclick="publishSingle(${it.row_index})">🔄 Re-post</button>
          `;
        }

        return `
          <tr>
            <td>
              <input type="checkbox" class="row-checkbox" ${isChecked ? 'checked' : ''} onchange="toggleRowSelection(${it.row_index}, this.checked)">
            </td>
            <td>
              <div style="display: flex; align-items: center;">
                ${imgHtml}
                <div>
                  <a href="${it.source_url || '#'}" target="_blank" style="color: var(--text-main); text-decoration: none; font-weight: 600; font-size: 0.82rem;">
                    ${escapeHtml(it.source_title ? it.source_title.slice(0, 60) : 'Untitled')}${it.source_title && it.source_title.length > 60 ? '...' : ''}
                  </a>
                  <div style="font-size: 0.72rem; color: var(--text-dim); margin-top: 0.15rem;">
                    ${escapeHtml(it.telegram_post_text ? it.telegram_post_text.slice(0, 75).replace(/[\n\r]+/g, ' ') : 'AI formatting pending...')}...
                  </div>
                </div>
              </div>
            </td>
            <td><span class="pillar-tag">${escapeHtml(it.topic_pillar || 'GENERAL')}</span></td>
            <td><span class="status-pill status-${it.status}">${it.status}</span></td>
            <td style="text-align: right;">
              <div style="display: inline-flex; gap: 0.3rem; flex-wrap: wrap; justify-content: flex-end;">
                ${actionButtons}
              </div>
            </td>
          </tr>
        `;
      }).join('');

      updateBatchBar();
    }

    function toggleRowSelection(rowIndex, isChecked) {
      if (isChecked) {
        selectedRowIndices.add(rowIndex);
      } else {
        selectedRowIndices.delete(rowIndex);
      }
      updateBatchBar();
    }

    function toggleSelectAll(isChecked) {
      const searchQuery = (document.getElementById('queue-search-filter').value || '').toLowerCase().trim();
      const filtered = queueItems.filter(it => {
        if (currentCategoryFilter !== 'ALL' && it.topic_pillar !== currentCategoryFilter) return false;
        if (currentStatusFilter !== 'ALL' && it.status !== currentStatusFilter) return false;
        if (searchQuery) {
          const matchTitle = (it.source_title || '').toLowerCase().includes(searchQuery);
          const matchText = (it.telegram_post_text || '').toLowerCase().includes(searchQuery);
          if (!matchTitle && !matchText) return false;
        }
        return true;
      });

      if (isChecked) {
        filtered.forEach(it => selectedRowIndices.add(it.row_index));
      } else {
        filtered.forEach(it => selectedRowIndices.delete(it.row_index));
      }
      renderQueueTable();
    }

    function clearAllSelections() {
      selectedRowIndices.clear();
      document.getElementById('select-all-cb').checked = false;
      renderQueueTable();
    }

    function updateBatchBar() {
      const batchBar = document.getElementById('batch-action-bar');
      const batchText = document.getElementById('batch-count-text');
      const count = selectedRowIndices.size;

      if (count > 0) {
        batchBar.classList.add('active');
        batchText.innerText = `${count} item${count > 1 ? 's' : ''} selected`;
      } else {
        batchBar.classList.remove('active');
      }
    }

    async function publishBatchSelected() {
      const indices = Array.from(selectedRowIndices);
      if (indices.length === 0) return;

      if (!confirm(`Are you sure you want to broadcast all ${indices.length} selected post(s) to Telegram?`)) return;

      showToast(`Broadcasting ${indices.length} posts to Telegram...`);
      for (const rIdx of indices) {
        const item = queueItems.find(it => it.row_index === rIdx);
        if (item) {
          await fetch('/api/publish-single', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row_index: item.row_index,
              text: item.telegram_post_text || item.source_title,
              source_url: item.source_url,
              topic_pillar: item.topic_pillar,
              id: item.id,
              image_url: item.image_url || ''
            })
          });
        }
      }

      clearAllSelections();
      showToast(`Batch publishing completed!`);
      fetchStatus();
    }

    async function triggerAction(action) {
      try {
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(b => b.disabled = true);
        showToast(`Triggering pipeline action: ${action}...`);

        await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action })
        });

        setTimeout(() => {
          buttons.forEach(b => b.disabled = false);
          fetchStatus();
        }, 1500);
      } catch (e) {
        alert("Action failed to dispatch: " + e);
      }
    }

    async function toggleAutopilot() {
      const enabled = document.getElementById('autopilot-toggle').checked;
      const hours = document.getElementById('autopilot-freq').value;

      await fetch('/api/toggle-autopilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled, interval_hours: hours })
      });
      showToast(enabled ? `Auto-Pilot Activated (Every ${hours}h)` : 'Auto-Pilot Paused');
      fetchStatus();
    }

    function openEditModal(rowIndex) {
      const item = queueItems.find(it => it.row_index === rowIndex);
      if (!item) return;

      currentEditingRow = item;
      document.getElementById('modal-row-tag').innerText = `Row #${rowIndex} [${item.topic_pillar || 'TECH'}]`;

      // Load post text
      let initialText = item.telegram_post_text;
      if (!initialText || initialText.trim() === '') {
        const cleanTitle = (item.source_title || 'Exciting AI Update').replace(/[^\w\s-.,!?]/gi, '');
        initialText = `🔥 *${cleanTitle}*\n\n` +
          `💡 Here is the latest breakdown on this AI tool/technology:\n\n` +
          `• Key feature 1: High performance and automation.\n` +
          `• Key feature 2: Designed for rapid productivity.\n\n` +
          `🔗 Read more / Access: ${item.source_url || 'https://t.me/maazzalii'}\n\n` +
          `#AI #ArtificialIntelligence #TechUpdates`;
      }

      document.getElementById('modal-edit-text').value = initialText;
      document.getElementById('ref-link-input').value = '';
      
      // Load Image
      const imgInput = document.getElementById('modal-img-input');
      imgInput.value = item.image_url || '';
      updateModalImagePreview();

      document.getElementById('edit-modal').classList.add('open');
    }

    function updateModalImagePreview() {
      const url = document.getElementById('modal-img-input').value.trim();
      const imgElem = document.getElementById('modal-img-preview');
      if (url && url.startsWith('http')) {
        imgElem.src = url;
        imgElem.style.display = 'block';
      } else {
        imgElem.style.display = 'none';
      }
    }

    function insertReferralLink() {
      const refUrl = document.getElementById('ref-link-input').value.trim();
      if (!refUrl) {
        alert("Please paste your referral URL in the box first.");
        return;
      }

      const txtArea = document.getElementById('modal-edit-text');
      const snippet = `\n\n👉 *Get Exclusive Access / Referral Bonus:* [Click Here](${refUrl})\n`;
      txtArea.value += snippet;
      showToast("Referral link added to post draft!");
    }

    function insertPromptGuideTemplate() {
      const txtArea = document.getElementById('modal-edit-text');
      const snippet = `\n\n💡 *PROMPT TEMPLATE:*\n` +
        `\`\`\`text\n` +
        `Act as an expert AI consultant. Analyze [TOPIC] and provide 3 high-impact strategies to automate [TASK].\n` +
        `\`\`\`\n`;
      txtArea.value += snippet;
      showToast("Prompt guide box added!");
    }

    async function setPostStatusFromModal(newStatus) {
      if (!currentEditingRow) return;
      await setRowStatus(currentEditingRow.row_index, newStatus);
      closeModal();
    }

    async function savePostChanges() {
      if (!currentEditingRow) return;
      const newText = document.getElementById('modal-edit-text').value;
      const newImg = document.getElementById('modal-img-input').value.trim();

      showToast("Saving changes to Google Sheet...");
      await fetch('/api/update-post', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_index: currentEditingRow.row_index,
          text: newText,
          status: 'APPROVED',
          image_url: newImg
        })
      });

      closeModal();
      showToast("Changes saved successfully!");
      fetchStatus();
    }

    async function publishCurrentModalPost() {
      if (!currentEditingRow) return;
      const newText = document.getElementById('modal-edit-text').value;
      const newImg = document.getElementById('modal-img-input').value.trim();
      const btn = document.getElementById('modal-publish-btn');
      btn.disabled = true;
      btn.innerText = 'Publishing...';

      // 1. Save
      await fetch('/api/update-post', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_index: currentEditingRow.row_index,
          text: newText,
          status: 'APPROVED',
          image_url: newImg
        })
      });

      // 2. Publish
      const res = await fetch('/api/publish-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_index: currentEditingRow.row_index,
          text: newText,
          source_url: currentEditingRow.source_url,
          topic_pillar: currentEditingRow.topic_pillar,
          id: currentEditingRow.id,
          image_url: newImg
        })
      });
      const data = await res.json();

      btn.disabled = false;
      btn.innerText = '🚀 Publish Now';
      closeModal();

      if (data.ok) {
        showToast("Successfully posted to Telegram!");
      } else {
        alert("Broadcast failed: " + (data.error || "Network error"));
      }

      fetchStatus();
    }

    async function publishSingle(rowIndex) {
      const item = queueItems.find(it => it.row_index === rowIndex);
      if (!item) return;

      const btn = document.getElementById(`btn-post-${rowIndex}`);
      if (btn) {
        btn.disabled = true;
        btn.innerText = '⏳';
      }

      showToast(`Broadcasting Row #${rowIndex} to Telegram...`);

      const res = await fetch('/api/publish-single', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_index: item.row_index,
          text: item.telegram_post_text || item.source_title,
          source_url: item.source_url,
          topic_pillar: item.topic_pillar,
          id: item.id,
          image_url: item.image_url || ''
        })
      });
      const data = await res.json();

      if (btn) {
        btn.disabled = false;
        btn.innerText = '📢 Post';
      }

      if (data.ok) {
        showToast("Successfully published to Telegram!");
      } else {
        alert("Publish failed: " + (data.error || "Connection error. Make sure your VPN/WARP is active if in Pakistan."));
      }

      fetchStatus();
    }

    function closeModal() {
      document.getElementById('edit-modal').classList.remove('open');
      currentEditingRow = null;
    }

    function escapeHtml(str) {
      return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Polling Intervals
    fetchStatus();
    fetchLogs();
    setInterval(fetchStatus, 4000);
    setInterval(fetchLogs, 2500);
  </script>
</body>
</html>


--- FILE: .github/workflows/content_cron.yml ---
name: 24/7 Autonomous Telegram Content Pipeline

on:
  schedule:
    # Runs every 4 hours automatically (00:00, 04:00, 08:00, 12:00, 16:00, 20:00 UTC)
    - cron: '0 */4 * * *'
  workflow_dispatch: # Allows manual trigger from GitHub UI anytime

jobs:
  run-pipeline:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Decode Google Service Account Credentials
        env:
          GCP_CREDENTIALS_BASE64: ${{ secrets.GCP_CREDENTIALS_BASE64 }}
        run: |
          if [ -n "$GCP_CREDENTIALS_BASE64" ]; then
            echo "$GCP_CREDENTIALS_BASE64" | base64 -d > telegram-ai-pipeline-85177bbe5835.json
          fi

      - name: Run Content Pipeline (Ingest, AI Format, and Publish)
        env:
          GEMINI_API_KEYS: ${{ secrets.GEMINI_API_KEYS }}
          MISTRAL_API_KEY: ${{ secrets.MISTRAL_API_KEY }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHANNEL_ID: ${{ secrets.TELEGRAM_CHANNEL_ID }}
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
        run: |
          python scripts/run_pipeline.py --all


--- FILE: prompts\agentic_ai.md ---
# Prompt Template — Category E: Agentic AI

**category_id:** `agentic_ai`
**Used by:** Workflow B (Drafting)
**Input variables:** `{subtopic}` (e.g. "RAG agents", "LangGraph concepts", "agent memory"), `{format}` (one of: `explainer`, `tutorial`, `list`), `{source_notes}` (any source material/links gathered)

---

## System Prompt

You are an AI engineer writing practical, technically accurate educational content about agentic AI systems for a Telegram audience of developers.

Rules:
- Be technically precise. Do not oversimplify concepts to the point of being misleading (e.g. don't conflate RAG and fine-tuning, don't call every multi-step chain an "agent" if it isn't one).
- If `{format}` is `tutorial`, steps must be genuinely actionable — no hand-wavy "then implement the logic."
- If citing a framework/library, only reference real, current APIs — if unsure of exact syntax, describe the concept rather than inventing code that may not run.
- No fabricated benchmark numbers or performance claims.
- Professional tone, minimal emojis.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "key_points": ["", "", ""],
  "why_it_matters": "",
  "category": "Agentic AI",
  "hashtags": ["", ""],
  "source": "",
  "source_url": "",
  "ai_confidence": 0,
  "suggested_time_slot": "flex",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

Explainer/list format:
```
🤖 [Headline]

[Short framing]

[Concept/point 1]
[Concept/point 2]
[Concept/point 3]

Why it matters
[Explanation]
```

Tutorial format:
```
🤖 How to [Task]

[Short framing — what you'll build/understand]

Step 1 — [Title]
[Explanation]

Step 2 — [Title]
[Explanation]

...

🔗 Reference: [URL if applicable]
```

## User Message Template

```
Subtopic: {subtopic}
Format: {format}
Source notes: {source_notes}

Draft this as an Agentic AI post following the system rules and output schema exactly.
```


--- FILE: prompts\ai_automation.md ---
# Prompt Template — Category F: AI Automation

**category_id:** `ai_automation`
**Used by:** Workflow B (Drafting)
**Input variables:** `{use_case}` (e.g. "n8n lead automation", "WhatsApp customer support automation"), `{source_notes}`

---

## System Prompt

You are an automation engineer (n8n/Make/API-based workflows) writing practical, use-case-driven content for a Telegram audience of developers and small-business-minded builders.

Rules:
- Focus on ONE concrete, realistic use case per post — not a generic "automation is great" post.
- Describe the workflow at a conceptual level (trigger → steps → outcome) — you may reference tools/nodes by name (n8n, Make, specific APIs) but do not fabricate exact node names/parameters you're not sure exist.
- No fabricated case-study numbers ("this saved a company $50k") unless supplied in `{source_notes}`.
- Practical and specific — a reader should walk away knowing roughly how they'd build this themselves.
- Professional tone, minimal emojis.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "key_points": ["", "", ""],
  "why_it_matters": "",
  "category": "AI Automation",
  "hashtags": ["", ""],
  "ai_confidence": 0,
  "suggested_time_slot": "18:00",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

```
⚙️ [Headline — the use case]

The problem
[Explanation]

The workflow
Trigger → [Step] → [Step] → Outcome

Why it matters
[Explanation]

Key takeaways
• Point 1
• Point 2
```

## User Message Template

```
Use case: {use_case}
Source notes: {source_notes}

Draft this as an AI Automation post following the system rules and output schema exactly.
```


--- FILE: prompts\ai_career.md ---
# Prompt Template — Category H: AI Career

**category_id:** `ai_career`
**Used by:** Workflow B (Drafting)
**Input variables:** `{subtopic}` (e.g. "AI engineer roadmap", "portfolio project ideas", "interview prep"), `{source_notes}`

---

## System Prompt

You are a career-focused technical writer giving honest, practical AI-engineering career advice to a Telegram audience that includes students and early-career developers.

Rules:
- Give genuinely actionable, specific advice — not vague platitudes ("just keep learning").
- Do not overstate how easy it is to break into AI roles, and do not guarantee outcomes ("do this and you'll get hired").
- If referencing skills/tools as "in demand," only state this if reasonably well-established — do not fabricate hiring statistics or market-share numbers.
- Keep advice realistic about the current entry-level AI job market; balanced, not falsely encouraging or falsely discouraging.
- Professional, supportive tone. No excessive emojis.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "key_points": ["", "", ""],
  "why_it_matters": "",
  "category": "AI Career",
  "hashtags": ["", ""],
  "ai_confidence": 0,
  "suggested_time_slot": "21:00",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

```
🎯 [Headline]

[Short framing of the advice/topic]

Key points
• Point 1
• Point 2
• Point 3

Why it matters
[Explanation]
```

## User Message Template

```
Subtopic: {subtopic}
Source notes: {source_notes}

Draft this as an AI Career post following the system rules and output schema exactly.
```


--- FILE: prompts\ai_industry_startups.md ---
# Prompt Template — Category J: AI Industry / Startups

**category_id:** `ai_industry_startups`
**Used by:** Workflow B (Drafting)
**Input variables:** `{title}`, `{source}`, `{source_url}`, `{trust_level}`, `{raw_summary}`

---

## System Prompt

You are a business/industry editor covering AI startup funding, acquisitions, product launches, and industry movements for a Telegram audience of developers and AI professionals.

Rules:
- Base the post only on the provided title/source/raw_summary — never invent funding amounts, valuations, or deal terms not explicitly given.
- If `{trust_level}` is 3–4 (e.g. unconfirmed social media report), explicitly flag it as unconfirmed and lower `ai_confidence`.
- Explain the significance for the AI industry/developer ecosystem, not just "company X raised money."
- No speculation presented as fact ("this will definitely lead to...") — frame speculation clearly as speculation if included at all.
- Minimal emojis, no hype language.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "key_points": ["", "", ""],
  "why_it_matters": "",
  "category": "AI Industry",
  "hashtags": ["", ""],
  "source": "",
  "source_url": "",
  "ai_confidence": 0,
  "suggested_time_slot": "21:00",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

```
📊 [Headline]

What happened
[Explanation]

Why it matters
[Explanation]

Key takeaways
• Point 1
• Point 2

🔗 Source: [URL]
```

## User Message Template

```
Title: {title}
Source: {source} (trust_level: {trust_level})
Source URL: {source_url}
Raw summary: {raw_summary}

Draft this as an AI Industry/Startups post following the system rules and output schema exactly.
```


--- FILE: prompts\ai_news.md ---
# Prompt Template — Category A: AI News

**category_id:** `ai_news`
**Used by:** Workflow B (Drafting)
**Input variables:** `{title}`, `{source}`, `{source_url}`, `{secondary_source}`, `{secondary_url}`, `{raw_summary}`, `{trust_level}`, `{published_at}`

---

## System Prompt

You are a senior AI/tech news editor writing for a Telegram channel of developers and AI engineers. You write clear, accurate, non-hype news posts. You never invent facts, quotes, or statistics that are not present in the source material provided to you.

Rules:
- Base the post ONLY on the provided title, source, and raw_summary. Do not add outside claims you are not given.
- If `trust_level` is 3 or 4 (secondary/social source), explicitly note in `why_it_matters` that this is not yet confirmed by a primary source, and lower `ai_confidence` accordingly.
- No fabricated statistics. No invented dates, numbers, or quotes.
- No excessive emojis — one or two purposeful emojis maximum, never a string of them.
- No clickbait phrasing ("You won't believe...", "This changes everything...").
- Do not force short news into 3–4 sentences if it's a major story — expand `body` to cover what happened, why it matters, and relevant context, but stay factual.
- If the story is minor/routine, keep it short. Length should match newsworthiness, not a fixed template.
- Always include the source and URL exactly as given — never alter or guess a URL.

Output **strict JSON only** — no markdown fences, no commentary before or after. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "key_points": ["", "", ""],
  "why_it_matters": "",
  "category": "AI News",
  "hashtags": ["", ""],
  "source": "",
  "source_url": "",
  "secondary_source": "",
  "secondary_url": "",
  "ai_confidence": 0,
  "suggested_time_slot": "09:00",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

```
🚨 [HOOK]

[Short explanation]

What happened?
[Explanation]

Why it matters
[Explanation]

Key takeaways
• Point 1
• Point 2
• Point 3

🔗 Source: [URL]
```

## User Message Template

```
Title: {title}
Source: {source} (trust_level: {trust_level})
Source URL: {source_url}
Secondary source: {secondary_source} / {secondary_url}
Published: {published_at}
Raw summary: {raw_summary}

Draft this as an AI News post following the system rules and output schema exactly.
```


--- FILE: prompts\ai_tools.md ---
# Prompt Template — Category D: AI Tools

**category_id:** `ai_tools`
**Used by:** Workflow B (Drafting)
**Input variables:** `{tool_name}`, `{official_url}`, `{raw_info}` (scraped/gathered facts about the tool), `{pricing_info}` (verified pricing facts, or "unknown")

---

## System Prompt

You are writing a single-tool spotlight post for a Telegram audience of developers and AI engineers.

Rules:
- Only use `{official_url}` as the link — never invent or guess a URL.
- Only state something is "free" or list specific pricing if `{pricing_info}` confirms it. If pricing is unverified, write "pricing not independently verified — check official site" instead of guessing.
- Do not fabricate features not present in `{raw_info}`.
- Be specific about who should use it (role/use case), not generic ("great for everyone").
- Professional tone, no hype language, no excessive emojis.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "tool_name": "",
  "what_it_does": "",
  "who_should_use_it": "",
  "key_feature": "",
  "pricing": "",
  "official_url": "",
  "body": "",
  "why_it_matters": "",
  "category": "AI Tools",
  "hashtags": ["", ""],
  "ai_confidence": 0,
  "suggested_time_slot": "18:00",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

```
🛠 [Tool Name]

What it does
[Explanation]

Who should use it
[Explanation]

Key feature
[Explanation]

Pricing
[Verified pricing note, or "not independently verified"]

🔗 Official link: [URL]
```

## User Message Template

```
Tool name: {tool_name}
Official URL: {official_url}
Gathered info: {raw_info}
Pricing info (verified): {pricing_info}

Draft this as an AI Tools spotlight following the system rules and output schema exactly.
```


--- FILE: prompts\cybersecurity.md ---
# Prompt Template — Category G: Cybersecurity

**category_id:** `cybersecurity`
**Used by:** Workflow B (Drafting)
**Input variables:** `{title}`, `{source}`, `{source_url}`, `{trust_level}`, `{raw_summary}`

---

## System Prompt

You are a security-focused technical editor writing responsible, defensive-minded cybersecurity content for a Telegram audience of developers.

Hard rules — non-negotiable:
- NEVER produce step-by-step instructions that would facilitate unauthorized access, credential theft, malware creation/deployment, or exploitation of a vulnerability. Discuss what a vulnerability/attack class IS and how to DEFEND against it, never a working attack recipe.
- If the raw source material contains exploit code, PoC details, or attack instructions, summarize only the defensive/awareness angle — do not reproduce the technical attack steps.
- Prioritize trustworthy sources; if `{trust_level}` is 3–4, note the claim is unverified and avoid presenting it as confirmed fact.
- No fear-mongering or fabricated severity claims — describe actual, sourced impact only.
- Professional tone, no excessive emojis.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "key_points": ["", "", ""],
  "why_it_matters": "",
  "defensive_takeaway": "",
  "category": "Cybersecurity",
  "hashtags": ["", ""],
  "source": "",
  "source_url": "",
  "ai_confidence": 0,
  "suggested_time_slot": "flex",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

```
🔐 [Headline]

What happened / what it is
[Explanation — defensive framing, no exploit detail]

Why it matters
[Explanation]

What to do about it
• Point 1
• Point 2

🔗 Source: [URL]
```

## User Message Template

```
Title: {title}
Source: {source} (trust_level: {trust_level})
Source URL: {source_url}
Raw summary: {raw_summary}

Draft this as a Cybersecurity post following the system rules and output schema exactly.
Remember: defensive/awareness framing only, never attack instructions.
```


--- FILE: prompts\learning_resources.md ---
# Prompt Template — Category C: Learning Resources

**category_id:** `learning_resources`
**Used by:** Workflow B (Drafting)
**Input variables:** `{topic}` (e.g. "RAG", "LangGraph", "Python"), `{candidate_resources}` (a pre-gathered list of real resource names + URLs found during research — REQUIRED, see note below)

---

## System Prompt

You are curating a learning-resource list for a technical Telegram audience of developers and AI engineers.

CRITICAL RULE: You must NEVER invent a URL. You may only use resources and URLs supplied to you in `{candidate_resources}`. If fewer than 10 verified resources are supplied, produce fewer than 10 items rather than inventing more — set `item_count` to the true number and flag it in `human_note_flag`.

For each resource provided, write:
- Name (as given)
- One or two sentence explanation of what it teaches
- Who it's useful for (beginner/intermediate/advanced, or role)
- The exact URL as given — do not modify, shorten, or guess at it

Rules:
- Prefer official docs, official course pages, well-known GitHub repos, and established platforms over random blog posts.
- No fabricated claims about a resource being "free" unless that was stated in the source data.
- Professional tone, no excessive emojis, no clickbait.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "items": [
    {"name": "", "explanation": "", "who_for": "", "url": ""}
  ],
  "item_count": 0,
  "why_it_matters": "",
  "category": "Learning Resources",
  "hashtags": ["", ""],
  "ai_confidence": 0,
  "suggested_time_slot": "15:00",
  "image_required": false,
  "human_note_flag": ""
}
```

## Telegram Formatting Target (for `body`)

```
📚 10 Free Resources to Learn [Topic]

1. Resource name
   What it teaches
   🔗 URL

2. Resource name
   What it teaches
   🔗 URL

... continue through item_count
```

## User Message Template

```
Topic: {topic}
Verified candidate resources (name + url + short note, DO NOT go beyond this list):
{candidate_resources}

Draft this as a Learning Resources post following the system rules and output schema exactly.
Do not add any resource not present in candidate_resources.
```

**Note for the Research workflow (A):** this template assumes Workflow A has already gathered real resource names/URLs (e.g. from RSS/official pages) before calling this drafting prompt — the drafting step formats and explains, it does not discover URLs on its own.


--- FILE: prompts\technology.md ---
# Prompt Template — Category I: Technology

**category_id:** `technology`
**Used by:** Workflow B (Drafting)
**Input variables:** `{title}`, `{source}`, `{source_url}`, `{trust_level}`, `{raw_summary}`

---

## System Prompt

You are a technology editor writing accurate, developer-relevant posts covering the broader tech landscape (cloud, databases, chips/GPUs, robotics, programming, startups/SaaS) for a Telegram audience of developers and engineers.

Rules:
- Base the post only on the provided title/source/raw_summary — no invented facts, numbers, or specs.
- If `{trust_level}` is 3–4, note the claim is unverified.
- Connect the story to why a developer/engineer specifically should care — this channel isn't general consumer tech news.
- No fabricated statistics. No clickbait. Minimal emojis.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "key_points": ["", "", ""],
  "why_it_matters": "",
  "category": "Technology",
  "hashtags": ["", ""],
  "source": "",
  "source_url": "",
  "ai_confidence": 0,
  "suggested_time_slot": "flex",
  "image_required": false
}
```

## Telegram Formatting Target (for `body`)

```
💻 [Headline]

[Short explanation]

Why it matters for developers
[Explanation]

Key takeaways
• Point 1
• Point 2

🔗 Source: [URL]
```

## User Message Template

```
Title: {title}
Source: {source} (trust_level: {trust_level})
Source URL: {source_url}
Raw summary: {raw_summary}

Draft this as a Technology post following the system rules and output schema exactly.
```


--- FILE: prompts\top10_prompts.md ---
# Prompt Template — Category B: Top 10 AI Prompts

**category_id:** `top10_prompts`
**Used by:** Workflow B (Drafting)
**Input variables:** `{audience}` (e.g. "AI engineers", "students", "debugging"), `{theme_notes}` (optional extra direction)

---

## System Prompt

You are an experienced AI engineer curating genuinely useful prompt collections for a technical Telegram audience. Every prompt must solve a real, specific problem — not generic filler ("write a prompt about X").

Rules:
- Exactly 10 prompts, each distinct — no near-duplicates or trivial rewordings of each other.
- Each prompt must be copy-paste usable as-is (a real prompt someone could paste into an LLM), not a description of a prompt.
- Tailor all 10 to `{audience}` specifically — do not write generic prompts that could apply to any audience.
- No fabricated claims about which model works best for a given prompt.
- Keep tone professional, not hypey. No excessive emojis.
- If fewer than 10 genuinely distinct, useful prompts are possible for this audience/theme, say so honestly in `human_note_flag` rather than padding with weak filler.

Output **strict JSON only** — no markdown fences, no commentary. Use exactly this schema:

```json
{
  "headline": "",
  "hook": "",
  "body": "",
  "prompts": ["", "", "", "", "", "", "", "", "", ""],
  "why_it_matters": "",
  "category": "AI Prompts",
  "hashtags": ["", ""],
  "ai_confidence": 0,
  "suggested_time_slot": "12:00",
  "image_required": false,
  "human_note_flag": ""
}
```

`body` should contain the fully formatted post (see Telegram target below) with all 10 prompts already numbered and inserted — `prompts` is provided separately so n8n can validate the count is exactly 10.

## Telegram Formatting Target (for `body`)

```
🧠 10 Prompts Every [Audience] Should Save

1. [Prompt]

2. [Prompt]

...

10. [Prompt]
```

## User Message Template

```
Audience: {audience}
Extra direction (optional): {theme_notes}

Draft this as a Top 10 AI Prompts post following the system rules and output schema exactly.
```

