"""
Lightweight Web Dashboard Server for Telegram AI Content Pipeline.

Provides a modern visual UI to monitor Content Queue, preview AI posts,
and trigger pipeline actions with 1-click from your browser (desktop & mobile).

Usage:
    python scripts/dashboard_server.py --port 8080
"""

import os
import sys
import json
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
SPREADSHEET_ID = "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE"

LATEST_LOGS = ["Dashboard server initialized. Ready for commands."]


def add_log(msg: str):
    global LATEST_LOGS
    LATEST_LOGS.append(msg)
    if len(LATEST_LOGS) > 100:
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


def fetch_sheet_queue() -> dict:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_path = BASE_DIR / CREDENTIALS_FILE
        if not creds_path.exists():
            return {"error": "Credentials file not found", "items": []}

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = service_account.Credentials.from_service_account_file(
            str(creds_path), scopes=scopes
        )
        service = build("sheets", "v4", credentials=creds)

        res = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="'Content_Queue'!A2:M"
        ).execute()
        rows = res.get("values", [])

        items = []
        pending_count = 0
        approved_count = 0
        published_count = 0

        for r in rows:
            status = r[7] if len(r) > 7 else "PENDING"
            if status == "PENDING":
                pending_count += 1
            elif status == "APPROVED":
                approved_count += 1
            elif status == "PUBLISHED":
                published_count += 1

            items.append({
                "id": r[0] if len(r) > 0 else "",
                "source_title": r[1] if len(r) > 1 else "",
                "source_url": r[2] if len(r) > 2 else "",
                "topic_pillar": r[3] if len(r) > 3 else "TECH",
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
            "items": items[::-1]  # Newest first
        }
    except Exception as e:
        return {"error": str(e), "items": [], "total": 0, "pending": 0, "approved": 0, "published": 0}


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

        # Serve static files from BASE_DIR
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
            action = payload.get("action", "all")

            run_pipeline_action_async(action)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "action": action}).encode("utf-8"))
            return


def run_server(port: int = 8080):
    server_address = ("", port)
    os.chdir(str(BASE_DIR))
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"\n" + "=" * 60)
    print(f"🌟 Telegram AI Pipeline Web Dashboard Running!")
    print(f"👉 Local Access:   http://localhost:{port}")
    print(f"👉 Mobile Access:  http://YOUR_LOCAL_IP:{port}")
    print("=" * 60 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Stopping Dashboard Server...")
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    run_server(args.port)
