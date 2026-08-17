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


def load_prompt_template(pillar: str) -> str:
    filename = PROMPT_MAP.get(pillar, "technology.md")
    prompt_path = PROMPTS_DIR / filename
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return "You are an expert tech curator for Telegram. Summarize the following news concisely with emojis, key takeaways, and relevant hashtags."


def clean_json_string(text: str) -> str:
    """Extracts valid JSON object from LLM string if wrapped in markdown code blocks or extra text."""
    text = text.strip()
    # Remove markdown code block fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    
    # Try to find the outermost { ... }
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text


def format_to_clean_telegram_post(raw_ai_text: str, fallback_title: str, source_url: str, pillar: str) -> str:
    """
    Parses JSON output from LLM and formats it into a clean, professional,
    high-engagement Telegram message.
    """
    emoji = PILLAR_EMOJIS.get(pillar, "⚡")
    json_candidate = clean_json_string(raw_ai_text)
    
    try:
        data = json.loads(json_candidate)
        headline = data.get("headline") or fallback_title
        hook = data.get("hook", "").strip()
        body = data.get("body", "").strip()
        why_it_matters = data.get("why_it_matters", "").strip()
        key_points = data.get("key_points", [])
        hashtags = data.get("hashtags", [])

        lines = []
        # Header
        lines.append(f"{emoji} *{headline}*\n")
        
        # Hook / Intro
        if hook:
            lines.append(f"{hook}\n")
        
        # If body is structured text, clean it up
        if body and body != hook:
            # If body already contains "What happened", use it cleanly
            lines.append(f"{body}\n")
        elif why_it_matters:
            lines.append(f"*Why it matters:*\n{why_it_matters}\n")

        # Key Takeaways
        if key_points and isinstance(key_points, list):
            # Check if key points are already in body
            clean_points = [p.strip().lstrip("•-* ") for p in key_points if p.strip()]
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
        clean_text = raw_ai_text.strip()
        clean_text = re.sub(r"^```(?:json)?", "", clean_text)
        clean_text = re.sub(r"```$", "", clean_text)
        # Ensure source url is included
        if source_url and source_url not in clean_text:
            clean_text += f"\n\n🔗 [Source]({source_url})"
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
