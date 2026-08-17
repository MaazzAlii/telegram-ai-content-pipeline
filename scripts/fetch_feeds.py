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
            description = ""

            title_node = item.find("title")
            link_node = item.find("link")
            desc_node = item.find("description") or item.find("{http://purl.org/rss/1.0/modules/content/}encoded")

            if title_node is not None and title_node.text:
                title = clean_html(title_node.text)
            if link_node is not None:
                link = link_node.text.strip() if link_node.text else link_node.attrib.get("href", "")
            if desc_node is not None and desc_node.text:
                description = clean_html(desc_node.text)

            if title and link:
                items.append({
                    "id": str(uuid.uuid4())[:8],
                    "source_title": title,
                    "source_url": link,
                    "topic_pillar": pillar,
                    "raw_text": description[:1000] if description else title,
                    "status": "PENDING",
                    "quality_score": 0.85,
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })
    except Exception as e:
        print(f"  [!] Failed fetching {feed_url}: {e}")
    
    return items


def get_existing_urls(service, spreadsheet_id: str) -> set:
    try:
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="'Content_Queue'!C2:C"
        ).execute()
        rows = res.get("values", [])
        return {r[0].strip() for r in rows if r and len(r) > 0 and r[0]}
    except Exception as e:
        print(f"[!] Note: No existing rows found in Content_Queue: {e}")
        return set()


def ingest_to_sheets(credentials_path: str, spreadsheet_id: str, max_per_feed: int = 2):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    print(f"\n[+] Connecting to Google Sheets...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    existing_urls = get_existing_urls(service, spreadsheet_id)
    print(f"[+] Found {len(existing_urls)} existing URLs in Content_Queue.")

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
            if entry["source_url"] not in existing_urls:
                existing_urls.add(entry["source_url"])
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
