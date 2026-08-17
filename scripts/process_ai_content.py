"""
AI Content Processor with Multi-Key Rotation & Waterfall Fallback Router.

Pipeline Routing Logic:
  1. Primary Pool: Cycles through all provided Gemini API Keys (auto-switches on 429 quota/rate limit).
  2. Fallback Tier 1: Mistral AI API (if all Gemini keys are exhausted).
  3. Fallback Tier 2: Groq Cloud Llama-3.3 (if Mistral fails or is exhausted).

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

# Force UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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


def get_gemini_keys() -> list:
    keys_str = load_env_var("GEMINI_API_KEYS") or load_env_var("GEMINI_API_KEY")
    if not keys_str:
        return []
    return [k.strip() for k in keys_str.split(",") if k.strip()]


def load_prompt_template(pillar: str) -> str:
    filename = PROMPT_MAP.get(pillar, "technology.md")
    prompt_path = PROMPTS_DIR / filename
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return "You are an expert tech curator for Telegram. Summarize the following news concisely with emojis, key takeaways, and relevant hashtags."


def generate_with_gemini_key(api_key: str, system_prompt: str, content: str) -> str:
    # Use latest Google Gemini 2.5 Flash
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


def generate_ai_post(system_prompt: str, content: str) -> tuple:
    gemini_keys = get_gemini_keys()
    mistral_key = load_env_var("MISTRAL_API_KEY")
    groq_key = load_env_var("GROQ_API_KEY")

    # 1. Try Gemini Keys in order
    for idx, key in enumerate(gemini_keys, start=1):
        try:
            print(f"    [AI Router] Attempting Gemini Key #{idx} ({key[:8]}...)...")
            post = generate_with_gemini_key(key, system_prompt, content)
            if post:
                return post, f"Gemini Key #{idx}"
        except Exception as e:
            print(f"    [AI Router] Gemini Key #{idx} failed / rate-limited: {e}")

    # 2. Fallback to Mistral AI
    if mistral_key:
        try:
            print(f"    [AI Router] ⚠️ All Gemini keys exhausted. Falling back to Mistral AI...")
            post = generate_with_mistral(mistral_key, system_prompt, content)
            if post:
                return post, "Mistral AI"
        except Exception as e:
            print(f"    [AI Router] Mistral fallback failed: {e}")

    # 3. Fallback to Groq Cloud
    if groq_key:
        try:
            print(f"    [AI Router] ⚠️ Mistral failed. Falling back to Groq Llama-3.3...")
            post = generate_with_groq(groq_key, system_prompt, content)
            if post:
                return post, "Groq Cloud"
        except Exception as e:
            print(f"    [AI Router] Groq fallback failed: {e}")

    return "", "None"


def process_queue(credentials_path: str, spreadsheet_id: str, limit: int = 10):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

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

            print(f"\n[+] Processing item {processed_count + 1}: \"{title[:60]}\" [{pillar}]")
            prompt_template = load_prompt_template(pillar)
            combined_content = f"Title: {title}\nURL: {url}\nSummary/Context: {raw_text}"
            
            ai_post, provider = generate_ai_post(prompt_template, combined_content)
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
                print(f"  [OK] Generated high-engagement post using {provider}! Updated row {idx} to APPROVED.")
                processed_count += 1
            else:
                print(f"  [!] Failed generating AI post for row {idx} across all providers.")

    print(f"\n[SUCCESS] Successfully formatted {processed_count} items with AI!\n")


def main():
    parser = argparse.ArgumentParser(description="Process pending items with AI waterfall router")
    parser.add_argument("--credentials", "-c", default="telegram-ai-pipeline-85177bbe5835.json")
    parser.add_argument("--sheet-id", "-s", default="1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE")
    parser.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()
    process_queue(args.credentials, args.sheet_id, args.limit)


if __name__ == "__main__":
    main()
