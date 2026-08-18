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

import hashlib

PILLAR_MAPPING = {
    "ai_news": "AI_NEWS",
    "ai_tools": "AI_TOOLS",
    "ai_industry_startups": "AI_INDUSTRY_STARTUPS",
    "agentic_ai": "AGENTIC_AI",
    "ai_automation": "AI_AUTOMATION",
    "ai_career": "AI_CAREER",
    "cybersecurity": "CYBERSECURITY",
    "learning_resources": "LEARNING_RESOURCES",
    "technology": "TECH_DEVELOPMENT",
    "tech_development": "TECH_DEVELOPMENT",
    "top10_prompts": "TOP10_PROMPTS",
}

# Domain keyword lists for pre-filtering (Fix 3: Source Curation & Category Pre-filter)
CATEGORY_KEYWORDS = {
    "AI_NEWS": ["ai", "artificial intelligence", "llm", "gpt", "gemini", "claude", "deepmind", "openai", "anthropic", "meta", "model", "neural", "machine learning", "gpu", "nvidia", "transformer", "genai", "diffusion"],
    "AI_TOOLS": ["tool", "app", "release", "software", "library", "framework", "platform", "extension", "plugin", "saas", "api", "ai", "model", "agent", "generator", "copilot"],
    "AI_INDUSTRY_STARTUPS": ["startup", "funding", "venture", "raised", "acquisition", "valuation", "seed", "series", "enterprise", "market", "hugging face", "y combinator", "round", "investor"],
    "AGENTIC_AI": ["agent", "agentic", "autonomous", "autogpt", "crewai", "langchain", "langgraph", "swarm", "reasoning", "tool use", "mcp", "multi-agent", "action"],
    "AI_AUTOMATION": ["automation", "workflow", "n8n", "zapier", "pipeline", "orchestration", "agent", "automate", "productivity", "bot", "integration", "flow"],
    "AI_CAREER": ["career", "job", "hire", "hiring", "salary", "engineer", "developer", "prompt engineer", "skills", "interview", "resume", "work", "roles", "talent"],
    "CYBERSECURITY": ["vulnerability", "cve", "malware", "ransomware", "hack", "breach", "exploit", "security", "zero-day", "patch", "phishing", "ddos", "backdoor", "threat", "infosec", "cyber", "authentication"],
    "LEARNING_RESOURCES": ["github", "tutorial", "guide", "paper", "arxiv", "course", "learn", "dataset", "benchmark", "python", "open source", "repo", "library", "cheatsheet"],
    "TECH_DEVELOPMENT": ["code", "developer", "programming", "software", "api", "framework", "cloud", "database", "linux", "architecture", "web", "ai", "tech", "hardware", "system", "performance", "backend", "frontend", "devops"],
    "TOP10_PROMPTS": ["prompt", "system prompt", "prompt engineering", "few-shot", "cot", "chain of thought", "jailbreak", "instruction", "llm", "prompts", "roleplay", "metaprompt"],
}

# Static off-topic blacklist (catches curiosities, wildfires, trebuchets, sports, etc.)
OFF_TOPIC_BLACKLIST = [
    "trebuchet", "wildfire", "celebrity", "hollywood", "horoscope", "astrology",
    "recipe", "cooking", "nba", "nfl", "premier league", "baseball", "cricket score",
    "olympics medal", "box office", "fashion week", "movie review", "diet plan"
]


def is_on_topic(title: str, text: str, pillar: str, trust_level: int = 2) -> bool:
    """Pre-filter candidate articles (Fix 3) to guarantee off-topic noise is discarded before queueing."""
    combined = f"{title} {text}".lower()
    
    # 1. Reject if blacklisted term is present
    for bad_term in OFF_TOPIC_BLACKLIST:
        if bad_term in combined:
            return False
            
    # 2. Official Lab sources (Trust Level 1) are inherently on-topic
    if trust_level == 1:
        return True

    # 3. Check for pillar keywords or general AI/tech signals
    pillar_keywords = CATEGORY_KEYWORDS.get(pillar, CATEGORY_KEYWORDS["TECH_DEVELOPMENT"])
    for kw in pillar_keywords:
        if kw in combined:
            return True
            
    # Also accept if general core AI terms match
    for core_kw in ["ai", "llm", "software", "code", "developer", "api", "security", "model"]:
        if re.search(r'\b' + re.escape(core_kw) + r'\b', combined):
            return True

    return False


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


def resolve_canonical_url(url: str) -> str:
    """
    Resolves Google News redirect/wrapper URLs (news.google.com/rss/articles/... or news.google.com/read/...)
    into the true canonical article source URL for accurate attribution and deduplication.
    """
    if not url:
        return ""
    
    url = url.strip()
    # Check if URL is a Google News wrapper
    if "news.google.com" in url.lower():
        try:
            from googlenewsdecoder import gnewsdecoder
            decoded = gnewsdecoder(url)
            if isinstance(decoded, dict) and decoded.get("status") and decoded.get("decoded_url"):
                canonical = decoded["decoded_url"].strip()
                if canonical.startswith("http"):
                    return canonical
        except Exception:
            pass

        # Fallback: attempt HTTP GET redirect resolution
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                final_url = resp.geturl()
                if final_url and "news.google.com" not in final_url:
                    return final_url
        except Exception:
            pass

    return url


import ssl

def fetch_rss_entries(feed_url: str, pillar: str, trust_level: int = 2, max_items: int = 3) -> list:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TelegramAIPipeline/1.0"}
    req = urllib.request.Request(feed_url, headers=headers)
    items = []
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            content = resp.read()
        
        root = ET.fromstring(content)
        channel = root.find("channel")
        if channel is not None:
            raw_items = channel.findall("item")
        else:
            raw_items = root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry")

        for item in raw_items:
            if len(items) >= max_items:
                break

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

            if not title or not link:
                continue

            # Category Pre-filter check (Fix 3)
            clean_desc = clean_html(raw_desc)
            if not is_on_topic(title, clean_desc, pillar, trust_level=trust_level):
                # Discard off-topic article immediately
                continue

            # Resolve Google News redirect wrapper to canonical article URL (Bug C)
            canonical_link = resolve_canonical_url(link)

            image_url = extract_image_url(item, raw_desc)
            # Prefix raw_text with image metadata if found
            content_text = f"[IMAGE: {image_url}]\n{clean_desc[:1000]}" if image_url else (clean_desc[:1000] if clean_desc else title)

            items.append({
                "id": str(uuid.uuid4())[:8],
                "source_title": title,
                "source_url": canonical_link,
                "topic_pillar": pillar,
                "raw_text": content_text,
                "image_url": image_url,
                "status": "PENDING",
                "quality_score": 0.85 if trust_level <= 2 else 0.75,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
    except Exception as e:
        print(f"  [!] Failed fetching {feed_url}: {e}")
    
    return items


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, hashes, and trailing slashes (Fix 2 Dedup)."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        query_params = urllib.parse.parse_qsl(parsed.query)
        # Strip all analytics and tracking parameters
        cleaned_params = [
            (k, v) for k, v in query_params 
            if not k.lower().startswith("utm_") 
            and k.lower() not in ("ref", "cmpid", "source", "fbclid", "gclid", "mc_cid", "mc_eid")
        ]
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
                norm_u = normalize_url(r[1])
                existing_urls.add(norm_u)
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
                norm_u = normalize_url(r[1])
                existing_urls.add(norm_u)
                existing_urls.add(r[1].strip())
    except Exception as e:
        pass

    return existing_urls, existing_titles


def ensure_credentials_file(path_str: str = "telegram-ai-pipeline-85177bbe5835.json") -> Path:
    """Ensures service account credentials exist on disk from env vars or base64."""
    p = Path(path_str)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / path_str
    if p.exists():
        return p

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
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return p

    return p


def fetch_by_keyword(keyword: str, pillar: str, credentials_path: str, spreadsheet_id: str, max_items: int = 5) -> dict:
    """Fetch live news from Google News RSS for any custom keyword or search topic."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if not keyword or not keyword.strip():
        return {"ok": False, "error": "Search keyword cannot be empty", "added": 0}

    creds_file = ensure_credentials_file(credentials_path)
    if not creds_file.exists():
        return {
            "ok": False,
            "error": "Google Service Account credentials missing. Please set GOOGLE_SERVICE_ACCOUNT_JSON or GCP_CREDENTIALS_BASE64 in your Render Environment Variables.",
            "added": 0
        }

    keyword = keyword.strip()
    encoded_query = urllib.parse.quote(keyword)
    feed_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    print(f"\n[+] Searching news for custom topic: '{keyword}' (Pillar: {pillar})...")
    entries = fetch_rss_entries(feed_url, pillar, max_items=max_items)

    if not entries:
        return {"ok": False, "error": f"No news found for '{keyword}'", "added": 0}

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        str(creds_file), scopes=scopes
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
        trust_level = src.get("trust_level", 2)
        print(f"  -> Fetching: {name} [{pillar}] (Trust Level {trust_level})")
        entries = fetch_rss_entries(feed_url, pillar, trust_level=trust_level, max_items=max_per_feed)
        
        for entry in entries:
            norm_u = normalize_url(entry["source_url"])
            norm_t = normalize_title(entry["source_title"])
            if (norm_u not in existing_urls and entry["source_url"] not in existing_urls) and (norm_t not in existing_titles):
                existing_urls.add(norm_u)
                existing_urls.add(entry["source_url"])
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
