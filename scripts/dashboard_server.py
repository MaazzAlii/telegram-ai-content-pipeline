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

def ensure_credentials_file() -> Path:
    """Ensures service account credentials exist on disk from env vars or base64."""
    creds_path = BASE_DIR / CREDENTIALS_FILE
    if creds_path.exists():
        return creds_path

    import base64
    content = (
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        or os.environ.get("GCP_CREDENTIALS_BASE64")
        or os.environ.get("GOOGLE_CREDENTIALS_BASE64")
        or ""
    ).strip()

    if content:
        if not content.startswith("{"):
            try:
                decoded = base64.b64decode(content).decode("utf-8")
                if decoded.startswith("{"):
                    content = decoded
            except Exception:
                pass
        if content.startswith("{"):
            with open(creds_path, "w", encoding="utf-8") as f:
                f.write(content)
            return creds_path

    return creds_path

ensure_credentials_file()

LATEST_LOGS = ["Dashboard control center active. Auto-Pilot ready."]

AUTOPILOT_CONFIG = {
    "enabled": os.environ.get("AUTOPILOT_ENABLED", "true").lower() in ("true", "1", "yes"),
    "interval_hours": int(os.environ.get("AUTOPILOT_INTERVAL_HOURS", 6)),  # 4 times/day max
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
        elif action == "evergreen":
            cmd.append("--evergreen")
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
            elif status.startswith("REJECTED"):
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


def set_single_post_status(row_index: int, new_status: str) -> tuple:
    """Set post status. Enforces validation gate if status is APPROVED."""
    try:
        service = get_sheets_service()
        if new_status == "APPROVED":
            from process_ai_content import validate_ai_response
            res = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'Content_Queue'!A{row_index}:M{row_index}"
            ).execute()
            row = res.get("values", [[]])[0]
            title = row[1] if len(row) > 1 else ""
            url = row[2] if len(row) > 2 else ""
            pillar = row[3] if len(row) > 3 else "TECH_DEVELOPMENT"
            post_text = row[6] if len(row) > 6 else ""

            if not post_text or not post_text.strip():
                add_log(f"[VALIDATION REJECTED] Row #{row_index} cannot be approved: Post text is empty. Run AI processing first.")
                return False, "Cannot approve empty post. Please run AI processing or edit post text first."

            is_valid, err_reason, clean_text, _ = validate_ai_response(post_text, title, url, pillar)
            if not is_valid:
                add_log(f"[VALIDATION REJECTED] Row #{row_index} approval blocked: {err_reason}")
                return False, f"Validation check failed: {err_reason}"

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'Content_Queue'!H{row_index}",
            valueInputOption="USER_ENTERED",
            body={"values": [[new_status]]}
        ).execute()
        add_log(f"[STATUS UPDATE] Row #{row_index} status updated to: {new_status}")
        return True, "OK"
    except Exception as e:
        add_log(f"[STATUS UPDATE ERROR] Row #{row_index}: {e}")
        return False, str(e)


def update_single_post(row_index: int, new_text: str, new_status: str = "APPROVED", new_image_url: str = "") -> tuple:
    try:
        service = get_sheets_service()
        if new_status == "APPROVED":
            from process_ai_content import validate_ai_response
            res = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'Content_Queue'!A{row_index}:D{row_index}"
            ).execute()
            row = res.get("values", [[]])[0]
            title = row[1] if len(row) > 1 else ""
            url = row[2] if len(row) > 2 else ""
            pillar = row[3] if len(row) > 3 else "TECH_DEVELOPMENT"

            is_valid, err_reason, clean_text, _ = validate_ai_response(new_text, title, url, pillar)
            if not is_valid:
                add_log(f"[UPDATE REJECTED] Row #{row_index} post text failed validation: {err_reason}")
                return False, f"Validation failed: {err_reason}"
            new_text = clean_text

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
        return True, "OK"
    except Exception as e:
        add_log(f"[SHEET UPDATE ERROR] {e}")
        return False, str(e)


def publish_single_post_by_row(row_index: int, post_text: str, source_url: str, pillar: str, post_id: str, image_url: str = ""):
    from process_ai_content import validate_ai_response, format_to_clean_telegram_post
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

    # Enforce strict validation gate before broadcast
    is_valid, err_reason, clean_text, _ = validate_ai_response(post_text, "", source_url, pillar)
    if not is_valid:
        add_log(f"[PUBLISH ABORTED] Row #{row_index} failed validation gate: {err_reason}")
        return {"ok": False, "error": f"Cannot broadcast unvalidated post: {err_reason}"}

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
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)

            if parsed.path == "/" or parsed.path == "/index.html":
                index_path = DASHBOARD_DIR / "index.html"
                if index_path.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    with open(index_path, "rb") as f:
                        self.wfile.write(f.read())
                    return
                else:
                    self.path = "/dashboard/index.html"
                    return super().do_GET()

            if parsed.path == "/api/status":
                data = fetch_sheet_queue()
                self._send_json(data)
                return

            if parsed.path == "/api/logs":
                self._send_json({"logs": LATEST_LOGS})
                return

            return super().do_GET()
        except Exception as e:
            self._send_json({"error": str(e), "ok": False}, status_code=500)

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
            payload = json.loads(body) if body else {}

            if parsed.path == "/api/run":
                action = payload.get("action", "all")
                run_pipeline_action_async(action)
                self._send_json({"status": "started", "action": action, "ok": True})
                return

            if parsed.path == "/api/set-status":
                row_idx = payload.get("row_index")
                new_status = payload.get("status", "APPROVED")
                ok, msg = set_single_post_status(row_idx, new_status)
                self._send_json({"ok": ok, "row_index": row_idx, "status": new_status, "error": msg if not ok else None})
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

            if parsed.path == "/api/generate-evergreen":
                pillar = payload.get("pillar", "TOP10_PROMPTS")
                topic = payload.get("topic", None)
                from generate_evergreen import generate_single_evergreen_post, append_evergreen_to_sheet
                add_log(f"\n[EVERGREEN QUEUE] Generating original content for [{pillar}]...")
                res = generate_single_evergreen_post(pillar, custom_topic=topic)
                if res.get("ok"):
                    append_evergreen_to_sheet(res, str(BASE_DIR / CREDENTIALS_FILE), SPREADSHEET_ID, status="APPROVED")
                    add_log(f"[EVERGREEN SUCCESS] Generated and approved original post: '{res.get('topic')}'")
                else:
                    add_log(f"[EVERGREEN ERROR] {res.get('error')}")
                self._send_json(res)
                return

            if parsed.path == "/api/update-post":
                row_idx = payload.get("row_index")
                new_text = payload.get("text", "")
                new_status = payload.get("status", "APPROVED")
                new_image_url = payload.get("image_url", "")
                ok, msg = update_single_post(row_idx, new_text, new_status, new_image_url)
                self._send_json({"ok": ok, "error": msg if not ok else None})
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

            # Fallback 404 for unknown POST endpoints
            self._send_json({"error": f"Unknown endpoint: {parsed.path}", "ok": False}, status_code=404)

        except Exception as e:
            add_log(f"[SERVER ERROR] {e}")
            self._send_json({"error": str(e), "ok": False}, status_code=500)

    def _send_json(self, data: dict, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
