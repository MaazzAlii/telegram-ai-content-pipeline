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
    "AI_NEWS": "ai_news.md",
    "AI_TOOLS": "ai_tools.md",
    "AI_INDUSTRY_STARTUPS": "ai_industry_startups.md",
    "AGENTIC_AI": "agentic_ai.md",
    "AI_AUTOMATION": "ai_automation.md",
    "AI_CAREER": "ai_career.md",
    "CYBERSECURITY": "cybersecurity.md",
    "LEARNING_RESOURCES": "learning_resources.md",
    "TECH_DEVELOPMENT": "technology.md",
    "TOP10_PROMPTS": "top10_prompts.md",
}

PILLAR_EMOJIS = {
    "AI_NEWS": "🚨",
    "AI_TOOLS": "🛠️",
    "AI_INDUSTRY_STARTUPS": "🚀",
    "AGENTIC_AI": "🤖",
    "AI_AUTOMATION": "⚙️",
    "AI_CAREER": "💼",
    "CYBERSECURITY": "🛡️",
    "LEARNING_RESOURCES": "📚",
    "TECH_DEVELOPMENT": "⚡",
    "TOP10_PROMPTS": "💡",
}

# Refusal & out-of-scope phrases (Fix 1 Stage 4)
REFUSAL_PHRASES = [
    "does not contain information",
    "not relevant to",
    "out of scope",
    "i cannot",
    "i'm unable to",
    "i am unable to",
    "no information provided",
    "topic out of scope",
    "as an ai",
    "as a language model",
    "i do not have enough information",
    "cannot fulfill this request",
    "does not mention",
    "is not mentioned in the provided text"
]


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
    """Loads system prompt verbatim from prompts/*.md per Fix 4."""
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
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text


# Category-specific length bounds: (min_body, max_body, min_total_post, max_total_post)
CATEGORY_LENGTH_BOUNDS = {
    "AI_NEWS": (300, 1800, 400, 2500),
    "TECH_DEVELOPMENT": (300, 1800, 400, 2500),
    "CYBERSECURITY": (300, 1800, 400, 2500),
    "AI_INDUSTRY_STARTUPS": (300, 1800, 400, 2500),
    "AGENTIC_AI": (300, 1800, 400, 2500),
    "AI_AUTOMATION": (300, 1800, 400, 2500),
    "AI_TOOLS": (200, 1200, 280, 2000),
    "LEARNING_RESOURCES": (200, 1200, 280, 2000),
    "AI_CAREER": (250, 2000, 350, 2800),
    "TOP10_PROMPTS": (250, 2400, 350, 3200),
}
DEFAULT_LENGTH_BOUNDS = (250, 1800, 350, 2500)


def validate_ai_response(raw_ai_text: str, fallback_title: str, source_url: str, pillar: str) -> tuple:
    """
    Strict multi-stage validation gate enforcing content quality, min/max length bounds,
    and structural integrity for both raw AI JSON output and manually edited/formatted posts.
    Returns: (is_valid: bool, error_reason: str, clean_formatted_post: str, parsed_json: dict)
    """
    if not raw_ai_text or not raw_ai_text.strip():
        return False, "Empty response or text", "", {}

    bounds = CATEGORY_LENGTH_BOUNDS.get(pillar, DEFAULT_LENGTH_BOUNDS)
    min_body, max_body, min_total, max_total = bounds

    # Check if text is JSON formatted
    json_candidate = clean_json_string(raw_ai_text)
    is_json = False
    data = {}
    try:
        parsed = json.loads(json_candidate)
        if isinstance(parsed, dict) and ("headline" in parsed or "body" in parsed):
            data = parsed
            is_json = True
    except Exception:
        is_json = False

    if is_json:
        # JSON validation path
        headline = sanitize_text(data.get("headline") or "")
        body = sanitize_text(data.get("body") or "")
        url = data.get("source_url") or data.get("url") or source_url or ""
        category = data.get("category") or pillar

        if not headline:
            return False, "Required Fields Check Failed: 'headline' is missing or empty", "", {}
        if not body:
            return False, "Required Fields Check Failed: 'body' is missing or empty (zero body content)", "", {}

        # URL check: evergreen prompts/career posts can use fallback/channel, others require source url
        if not url and pillar not in ("TOP10_PROMPTS", "AI_CAREER"):
            return False, "Required Fields Check Failed: 'source_url' is missing or empty", "", {}

        # Refusal Check (stage 3)
        combined_content = f"{headline} {body} {data.get('hook', '')} {data.get('why_it_matters', '')}".lower()
        for refusal in REFUSAL_PHRASES:
            if refusal in combined_content:
                return False, f"Refusal/Out-of-Scope Check Failed: matches '{refusal}'", "", {}

        # Min & Max Body Length Check (stage 4)
        body_len = len(body)
        if body_len < min_body:
            return False, f"Body Length Check Failed: body length ({body_len} chars) is under minimum threshold ({min_body} chars) for {pillar}", "", {}
        if body_len > max_body:
            return False, f"Body Length Check Failed: body length ({body_len} chars) exceeds maximum threshold ({max_body} chars) for {pillar}", "", {}

        # Build clean Telegram formatted post
        emoji = PILLAR_EMOJIS.get(pillar, "⚡")
        hook = sanitize_text(data.get("hook", ""))
        why_it_matters = sanitize_text(data.get("why_it_matters", ""))
        key_points = data.get("key_points", [])
        hashtags = data.get("hashtags", [])

        lines = [f"{emoji} *{headline}*\n"]

        if hook and hook != headline:
            lines.append(f"{hook}\n")

        if body and body != hook and body != headline:
            body_clean = re.sub(r"(?i)\*?Key takeaways\*?:\s*", "", body).strip()
            lines.append(f"{body_clean}\n")
        elif why_it_matters:
            lines.append(f"*Why it matters:*\n{why_it_matters}\n")

        if key_points and isinstance(key_points, list):
            clean_points = [sanitize_text(p).lstrip("•-* ") for p in key_points if p and p.strip()]
            clean_points = [p for p in clean_points if p and p != headline]
            if clean_points and not any(p in body for p in clean_points[:2]):
                lines.append("*Key Takeaways:*")
                for pt in clean_points[:4]:
                    lines.append(f"• {pt}")
                lines.append("")

        if url:
            lines.append(f"🔗 [Read Full Article]({url})\n")

        if hashtags and isinstance(hashtags, list):
            clean_tags = []
            for tag in hashtags:
                if not tag:
                    continue
                tag_str = str(tag).strip().lstrip("#").replace(" ", "").replace("-", "")
                if tag_str:
                    clean_tags.append(f"#{tag_str}")
            if clean_tags:
                lines.append(" ".join(clean_tags))
        else:
            lines.append(f"#{pillar.replace('_', '')} #TechNews #AI")

        formatted_post = "\n".join(lines).strip()
        total_len = len(formatted_post)
        if total_len < min_total:
            return False, f"Total Post Length ({total_len} chars) is below minimum {min_total} chars", "", {}
        if total_len > max_total:
            return False, f"Total Post Length ({total_len} chars) exceeds maximum {max_total} chars", "", {}

        return True, "OK", formatted_post, data

    else:
        # Pre-formatted text path (e.g. manually edited or already assembled)
        clean_text = sanitize_text(raw_ai_text)
        total_len = len(clean_text)

        # Refusal check
        lower_text = clean_text.lower()
        for refusal in REFUSAL_PHRASES:
            if refusal in lower_text:
                return False, f"Refusal/Out-of-Scope Check Failed: matches '{refusal}'", "", {}

        # Must have sufficient body length (prevent empty body / title-only posts)
        if total_len < min_total:
            return False, f"Post text length ({total_len} chars) is below minimum {min_total} chars for {pillar}", "", {}
        if total_len > max_total:
            return False, f"Post text length ({total_len} chars) exceeds maximum {max_total} chars for {pillar}", "", {}

        # Check that post is not just a link or single line
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        if len(lines) < 2:
            return False, "Post format invalid: Post contains fewer than 2 distinct lines (missing body)", "", {}

        return True, "OK", clean_text, {}


def format_to_clean_telegram_post(raw_ai_text: str, fallback_title: str, source_url: str, pillar: str) -> str:
    """Formats AI response into clean Telegram post passing validation gate."""
    is_valid, error, clean_post, _ = validate_ai_response(raw_ai_text, fallback_title, source_url, pillar)
    if is_valid:
        return clean_post
    return sanitize_text(raw_ai_text)


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
    """
    Executes AI Router through fallback providers and runs the 5-stage validation gate.
    Returns: (formatted_post, provider_name, is_valid, error_reason)
    """
    gemini_keys = get_gemini_keys()
    mistral_key = load_env_var("MISTRAL_API_KEY")
    groq_key = load_env_var("GROQ_API_KEY")

    last_error = "No AI providers configured or available"

    # 1. Try Gemini Keys in order
    for idx, key in enumerate(gemini_keys, start=1):
        try:
            print(f"    [AI Router] Attempting Gemini Key #{idx} ({key[:8]}...)...")
            raw_output = generate_with_gemini_key(key, system_prompt, content)
            if raw_output:
                is_valid, err_reason, clean_post, _ = validate_ai_response(raw_output, title, url, pillar)
                if is_valid:
                    return clean_post, f"Gemini Key #{idx}", True, "OK"
                else:
                    print(f"    [Validation Gate] ❌ Gemini Key #{idx} output failed validation: {err_reason}")
                    last_error = f"Gemini Key #{idx} validation error: {err_reason}"
        except Exception as e:
            print(f"    [AI Router] Gemini Key #{idx} failed / rate-limited: {e}")
            last_error = str(e)

    # 2. Fallback to Mistral AI
    if mistral_key:
        try:
            print(f"    [AI Router] ⚠️ Gemini exhausted. Falling back to Mistral AI...")
            raw_output = generate_with_mistral(mistral_key, system_prompt, content)
            if raw_output:
                is_valid, err_reason, clean_post, _ = validate_ai_response(raw_output, title, url, pillar)
                if is_valid:
                    return clean_post, "Mistral AI", True, "OK"
                else:
                    print(f"    [Validation Gate] ❌ Mistral AI output failed validation: {err_reason}")
                    last_error = f"Mistral AI validation error: {err_reason}"
        except Exception as e:
            print(f"    [AI Router] Mistral fallback failed: {e}")
            last_error = str(e)

    # 3. Fallback to Groq Cloud
    if groq_key:
        try:
            print(f"    [AI Router] ⚠️ Mistral exhausted. Falling back to Groq Llama-3.3...")
            raw_output = generate_with_groq(groq_key, system_prompt, content)
            if raw_output:
                is_valid, err_reason, clean_post, _ = validate_ai_response(raw_output, title, url, pillar)
                if is_valid:
                    return clean_post, "Groq Cloud", True, "OK"
                else:
                    print(f"    [Validation Gate] ❌ Groq output failed validation: {err_reason}")
                    last_error = f"Groq validation error: {err_reason}"
        except Exception as e:
            print(f"    [AI Router] Groq fallback failed: {e}")
            last_error = str(e)

    return "", "None", False, last_error


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
    rejected_count = 0

    for idx, row in enumerate(rows, start=2):
        if processed_count >= limit:
            break

        # Schema: id(0), source_title(1), source_url(2), topic_pillar(3), raw_text(4), ai_summary(5), telegram_post_text(6), status(7)... error_log(12)
        status = row[7] if len(row) > 7 else ""
        if status == "PENDING":
            title = row[1] if len(row) > 1 else ""
            url = row[2] if len(row) > 2 else ""
            pillar = row[3] if len(row) > 3 else "TECH_DEVELOPMENT"
            raw_text = row[4] if len(row) > 4 else title

            print(f"\n[+] Processing item {processed_count + 1}: \"{title[:60]}\" [{pillar}]")
            prompt_template = load_prompt_template(pillar)
            combined_content = f"Title: {title}\nURL: {url}\nSummary/Context: {raw_text}"
            
            ai_post, provider, is_valid, err_reason = generate_ai_post(prompt_template, combined_content, title, url, pillar)
            if is_valid and ai_post:
                # Update status to APPROVED, ai_summary, telegram_post_text, clear error_log
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'Content_Queue'!F{idx}:H{idx}",
                    valueInputOption="USER_ENTERED",
                    body={
                        "values": [[raw_text[:250], ai_post, "APPROVED"]]
                    }
                ).execute()
                # Clear error_log column M (col 13)
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'Content_Queue'!M{idx}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[""]]}
                ).execute()
                print(f"  [OK] ✅ Validation Gate Passed via {provider}! Row {idx} marked APPROVED.")
                processed_count += 1
            else:
                # Reject row and write error reason into error_log so it NEVER reaches publishing
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'Content_Queue'!H{idx}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [["REJECTED_VALIDATION"]]}
                ).execute()
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'Content_Queue'!M{idx}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [[f"Validation Gate: {err_reason}"]]}
                ).execute()
                print(f"  [!] ❌ Validation Gate REJECTED row {idx}: {err_reason}. Marked REJECTED_VALIDATION.")
                rejected_count += 1

    print(f"\n[SUMMARY] AI Processing Complete: {processed_count} approved, {rejected_count} rejected by Validation Gate.\n")


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
