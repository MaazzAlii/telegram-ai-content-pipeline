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
