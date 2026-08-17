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

        for idx, r in enumerate(rows, start=2):
            status = r[7] if len(r) > 7 else "PENDING"
            if status == "PENDING":
                pending_count += 1
            elif status == "APPROVED":
                approved_count += 1
            elif status == "PUBLISHED":
                published_count += 1

            items.append({
                "row_index": idx,
                "id": r[0] if len(r) > 0 else "",
                "source_title": r[1] if len(r) > 1 else "",
                "source_url": r[2] if len(r) > 2 else "",
                "topic_pillar": r[3] if len(r) > 3 else "TECH_DEVELOPMENT",
                "raw_text": r[4] if len(r) > 4 else "",
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
            "autopilot": AUTOPILOT_CONFIG,
            "items": items[::-1]  # Newest first
        }
    except Exception as e:
        return {"error": str(e), "items": [], "total": 0, "pending": 0, "approved": 0, "published": 0, "autopilot": AUTOPILOT_CONFIG}


def update_single_post(row_index: int, new_text: str, new_status: str = "APPROVED") -> bool:
    try:
        service = get_sheets_service()
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'Content_Queue'!G{row_index}:H{row_index}",
            valueInputOption="USER_ENTERED",
            body={"values": [[new_text, new_status]]}
        ).execute()
        add_log(f"[SHEET UPDATE] Row {row_index} updated & set to {new_status}")
        return True
    except Exception as e:
        add_log(f"[SHEET UPDATE ERROR] {e}")
        return False


def publish_single_post_by_row(row_index: int, post_text: str, source_url: str, pillar: str, post_id: str) -> dict:
    from publish_telegram import send_telegram_message, load_env_var
    import datetime

    bot_token = load_env_var("TELEGRAM_BOT_TOKEN")
    channel_id = load_env_var("TELEGRAM_CHANNEL_ID")

    if not bot_token or not channel_id:
        return {"ok": False, "error": "Bot credentials missing in .env"}

    add_log(f"\n[SINGLE PUBLISH] Broadcasting row {row_index} to {channel_id}...")
    res = send_telegram_message(bot_token, channel_id, post_text)
    
    if res.get("ok"):
        msg_id = res.get("result", {}).get("message_id", "")
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        add_log(f"  [SUCCESS] Message #{msg_id} published live to Telegram!")

        # Update sheet status
        try:
            service = get_sheets_service()
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'Content_Queue'!H{row_index}:L{row_index}",
                valueInputOption="USER_ENTERED",
                body=[["PUBLISHED", 0.95, "", now_iso, now_iso]]
            ).execute()

            # Append to Published_Archive
            archive_row = [post_id, str(msg_id), pillar, post_text, source_url, now_iso, 0, 0, 0]
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

        if parsed.path == "/api/update-post":
            row_idx = payload.get("row_index")
            new_text = payload.get("text", "")
            new_status = payload.get("status", "APPROVED")
            ok = update_single_post(row_idx, new_text, new_status)
            self._send_json({"ok": ok})
            return

        if parsed.path == "/api/publish-single":
            row_idx = payload.get("row_index")
            text = payload.get("text", "")
            url = payload.get("source_url", "")
            pillar = payload.get("topic_pillar", "TECH")
            post_id = payload.get("id", "")
            res = publish_single_post_by_row(row_idx, text, url, pillar, post_id)
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
