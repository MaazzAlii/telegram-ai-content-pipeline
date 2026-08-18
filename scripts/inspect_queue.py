import sys
import os
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2 import service_account
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent.parent
creds_file = BASE_DIR / "telegram-ai-pipeline-85177bbe5835.json"
sheet_id = "1hyAJO20O7mjbMF-BScot82wWtAij_NpBSYJhhfWUXxE"
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = service_account.Credentials.from_service_account_file(str(creds_file), scopes=scopes)
service = build("sheets", "v4", credentials=creds)

res = service.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Content_Queue'!A1:M").execute()
rows = res.get("values", [])
print(f"Total rows in Content_Queue: {len(rows)}")

approved = []
rejected = []
pending = []

for idx, r in enumerate(rows[1:], start=2):
    status = r[7].strip() if len(r) > 7 and r[7] else "PENDING"
    title = r[1] if len(r) > 1 else ""
    post_text = r[6] if len(r) > 6 else ""
    error_log = r[12] if len(r) > 12 else ""
    pillar = r[3] if len(r) > 3 else ""
    if status == "APPROVED":
        approved.append({"row": idx, "title": title, "pillar": pillar, "post_text": post_text})
    elif "REJECT" in status:
        rejected.append({"row": idx, "title": title, "error": error_log})
    else:
        pending.append({"row": idx, "title": title, "pillar": pillar})

print(f"APPROVED count: {len(approved)}")
print(f"REJECTED count: {len(rejected)}")
print(f"PENDING count: {len(pending)}")

print("\n" + "="*70)
print("APPROVED POSTS CURRENTLY QUEUED (Exact Formatted Content)")
print("="*70)
for a in approved[:5]:
    print(f"\n[Row {a['row']} - Pillar: {a['pillar']}] {a['title']}")
    print(a['post_text'])
    print("-" * 50)

print("\n" + "="*70)
print("REJECTED / DISCARDED ITEMS IN QUEUE")
print("="*70)
if not rejected:
    print("None in current queue (pre-filter prevented rejected items from entering queue).")
else:
    for r in rejected:
        print(f"Row {r['row']}: {r['title']} -> Reason: {r['error']}")
