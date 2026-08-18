"""
Evergreen / Original Topic Queue Content Generator for Telegram AI Pipeline.

Generates original, high-value technical posts directly from the AI model's knowledge base
using curated rotating topics from config/evergreen_topics.yaml and prompt templates from prompts/*.
"""

import os
import sys
import json
import uuid
import datetime
import argparse
from pathlib import Path
import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "evergreen_topics.yaml"
STATE_FILE = BASE_DIR / "config" / ".evergreen_state.json"
SCRIPTS_DIR = BASE_DIR / "scripts"
CREDENTIALS_FILE = BASE_DIR / "telegram-ai-pipeline-85177bbe5835.json"
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")

sys.path.insert(0, str(SCRIPTS_DIR))
from process_ai_content import (
    load_prompt_template,
    generate_ai_post,
    validate_ai_response,
    load_env_var
)


def load_evergreen_topics() -> dict:
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Evergreen topics config missing at {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("evergreen_topics", {})


def load_rotation_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_rotation_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Could not save rotation state: {e}")


def get_next_topic_for_pillar(pillar: str, custom_topic: str = None) -> tuple:
    """Returns (topic_dict, next_index) using round-robin rotation."""
    all_topics = load_evergreen_topics()
    pillar_topics = all_topics.get(pillar, [])

    if not pillar_topics:
        # Fallback if pillar not explicitly in config
        return {"topic": custom_topic or f"Modern AI techniques for {pillar}"}, 0

    if custom_topic:
        return {"topic": custom_topic, "notes": "Custom user-requested topic"}, 0

    state = load_rotation_state()
    cur_idx = state.get(pillar, 0)
    topic_item = pillar_topics[cur_idx % len(pillar_topics)]
    next_idx = (cur_idx + 1) % len(pillar_topics)

    state[pillar] = next_idx
    save_rotation_state(state)

    return topic_item, next_idx


def generate_single_evergreen_post(pillar: str, custom_topic: str = None) -> dict:
    """
    Generates and validates an original post for a given evergreen pillar.
    Returns: {"ok": bool, "pillar": str, "topic": str, "post_text": str, "provider": str, "error": str}
    """
    topic_info, _ = get_next_topic_for_pillar(pillar, custom_topic)
    topic_title = topic_info.get("topic") if isinstance(topic_info, dict) else str(topic_info)
    audience = topic_info.get("audience", "AI Developers & Technical Enthusiasts") if isinstance(topic_info, dict) else "Technical Audience"
    subtopic = topic_info.get("subtopic", topic_title) if isinstance(topic_info, dict) else topic_title
    notes = topic_info.get("notes", "") if isinstance(topic_info, dict) else ""

    print(f"\n[+] Generating Evergreen Content for [{pillar}]...")
    print(f"    Topic: \"{topic_title}\"")
    if notes:
        print(f"    Direction: {notes}")

    prompt_template = load_prompt_template(pillar)
    prompt_template = prompt_template.replace("{audience}", audience).replace("{subtopic}", subtopic).replace("{topic}", topic_title).replace("{theme_notes}", notes).replace("{source_notes}", notes)

    user_context = (
        f"Topic: {topic_title}\n"
        f"Audience / Subtopic: {subtopic}\n"
        f"Specific Focus & Guidelines: {notes}\n"
        f"Draft a comprehensive, highly actionable, and professional Telegram broadcast post matching the required schema."
    )

    # Execute Waterfall Router
    clean_post, provider, is_valid, err_reason = generate_ai_post(
        system_prompt=prompt_template,
        content=user_context,
        title=topic_title,
        url="",  # Evergreen original content has no external RSS URL
        pillar=pillar
    )

    if not is_valid:
        return {
            "ok": False,
            "pillar": pillar,
            "topic": topic_title,
            "error": err_reason,
            "provider": provider
        }

    return {
        "ok": True,
        "pillar": pillar,
        "topic": topic_title,
        "post_text": clean_post,
        "provider": provider,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


def append_evergreen_to_sheet(post_data: dict, credentials_path: str, spreadsheet_id: str, status: str = "APPROVED") -> bool:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = Path(credentials_path)
    if not creds_path.is_absolute():
        creds_path = BASE_DIR / credentials_path

    if not creds_path.exists():
        print(f"[!] Service account file not found at {creds_path}")
        return False

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    post_id = str(uuid.uuid4())[:8]
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    row = [
        post_id,
        post_data["topic"],
        "https://t.me/maazzalii",  # Channel reference URL for original evergreen posts
        post_data["pillar"],
        f"[EVERGREEN ORIGINAL] {post_data['topic']}",
        post_data["topic"][:250],
        post_data["post_text"],
        status,
        0.95,
        now_iso,
        "",  # scheduled_at
        "",  # published_at
        ""   # error_log
    ]

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="'Content_Queue'!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()

    print(f"  [OK] ✅ Appended evergreen post '{post_data['topic'][:50]}' as {status} to Google Sheet!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate original evergreen content using Topic Queue")
    parser.add_argument("--pillar", "-p", default="TOP10_PROMPTS", choices=["TOP10_PROMPTS", "AI_CAREER", "LEARNING_RESOURCES", "AGENTIC_AI", "AI_AUTOMATION", "all"], help="Category pillar")
    parser.add_argument("--topic", "-t", default=None, help="Optional custom topic override")
    parser.add_argument("--dry-run", action="store_true", help="Generate and print post without saving to Google Sheets")
    parser.add_argument("--status", default="APPROVED", choices=["APPROVED", "PENDING"], help="Queue status for new post")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json")
    parser.add_argument("--sheet-id", "-s", default=SPREADSHEET_ID)

    args = parser.parse_args()

    pillars_to_run = [args.pillar] if args.pillar != "all" else ["TOP10_PROMPTS", "AI_CAREER", "LEARNING_RESOURCES"]

    print("\n" + "=" * 60)
    print("🌟 Evergreen Topic Queue — Original AI Content Engine")
    print(f"👉 Pillars: {', '.join(pillars_to_run)}")
    print(f"👉 Mode: {'DRY RUN (Preview Only)' if args.dry_run else 'LIVE SHEET APPEND'}")
    print("=" * 60)

    for p in pillars_to_run:
        res = generate_single_evergreen_post(p, custom_topic=args.topic)
        if res["ok"]:
            print(f"\n--- [GENERATED POST: {p}] ---")
            print(res["post_text"])
            print("------------------------------------------\n")
            if not args.dry_run:
                append_evergreen_to_sheet(res, args.credentials, args.sheet_id, status=args.status)
        else:
            print(f"[!] ❌ Generation failed for {p}: {res.get('error')}")


if __name__ == "__main__":
    main()
