"""
AI Content Processor for Telegram AI Content Pipeline.

Reads PENDING items from Content_Queue in Google Sheets, loads the corresponding
topic prompt template from prompts/, generates high-engagement Telegram posts
using Gemini / AI LLM, and updates the Google Sheet with status APPROVED.

Usage:
    python scripts/process_ai_content.py --sheet-id 1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

PROMPT_MAP = {
    "AI_TOOLS": "ai_tools.md",
    "AI_INDUSTRY_STARTUPS": "ai_industry_startups.md",
    "CYBERSECURITY": "cybersecurity.md",
    "LEARNING_RESOURCES": "learning_resources.md",
    "TECH_DEVELOPMENT": "technology.md",
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


def load_prompt_template(pillar: str) -> str:
    filename = PROMPT_MAP.get(pillar, "technology.md")
    prompt_path = PROMPTS_DIR / filename
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return "You are an expert tech curator for Telegram. Summarize the following news concisely with emojis, key takeaways, and relevant hashtags."


def call_gemini_api(api_key: str, prompt: str, content: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{prompt}\n\n---\nRAW ARTICLE CONTENT:\n{content}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 800
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
    except Exception as e:
        print(f"[!] Gemini API Error: {e}")
    return ""


def process_queue(credentials_path: str, spreadsheet_id: str, limit: int = 5):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    gemini_key = load_env_var("GEMINI_API_KEY")
    if not gemini_key:
        print("\n[!] Note: GEMINI_API_KEY is not set in .env yet.")
        print("    Add your free Gemini API key to .env (from https://aistudio.google.com/) to enable live AI post generation.")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
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

            print(f"\n[+] Processing item {processed_count + 1}: {title[:50]}... [{pillar}]")
            prompt_template = load_prompt_template(pillar)
            combined_content = f"Title: {title}\nURL: {url}\nSummary: {raw_text}"
            
            ai_post = call_gemini_api(gemini_key, prompt_template, combined_content)
            if ai_post:
                # Update status to APPROVED, ai_summary, telegram_post_text
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'Content_Queue'!F{idx}:H{idx}",
                    valueInputOption="USER_ENTERED",
                    body={
                        "values": [[raw_text[:200], ai_post, "APPROVED"]]
                    }
                ).execute()
                print(f"  [OK] Generated Telegram post & updated row {idx} to APPROVED!")
                processed_count += 1
            else:
                print(f"  [!] Failed generating AI post for row {idx}.")

    print(f"\n[SUCCESS] Processed {processed_count} items with AI formatting!\n")


def main():
    parser = argparse.ArgumentParser(description="Process pending items with AI")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json")
    parser.add_argument("--sheet-id", "-s", default="1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")
    parser.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()
    process_queue(args.credentials, args.sheet_id, args.limit)


if __name__ == "__main__":
    main()
