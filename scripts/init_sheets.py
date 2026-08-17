"""
Google Sheets Initializer for Telegram AI Content Pipeline.

Initializes the required 4 tabs, column headers, styling, and default topic pillars
either directly via Google Sheets API (using Service Account JSON) or by generating
ready-to-import CSV files.

Usage:
    # 1. Direct API Initialization:
    python scripts/init_sheets.py --credentials path/to/service-account.json --sheet-id YOUR_SPREADSHEET_ID

    # 2. Generate CSVs for manual 1-click Import:
    python scripts/init_sheets.py --export-csv
"""

import os
import sys
import json
import csv
import argparse
from pathlib import Path

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "config" / "sheets_schema.json"


def load_schema() -> dict:
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_FILE}")
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def export_csv_templates(schema: dict, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[+] Exporting CSV templates to: {output_dir}")

    for tab_name, tab_data in schema.get("tabs", {}).items():
        csv_path = output_dir / f"{tab_name}.csv"
        headers = tab_data.get("headers", [])
        default_data = tab_data.get("default_data", [])

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in default_data:
                writer.writerow(row)

        print(f"  -> Created {csv_path.name} ({len(headers)} columns)")

    print("\n[OK] CSV templates generated! You can import them directly into Google Sheets:")
    print("     Open Google Sheets -> File -> Import -> Upload -> Select CSV -> Insert new sheet(s).\n")


def init_via_google_api(credentials_path: str, spreadsheet_id: str, schema: dict):
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("\n[!] Google API libraries not installed. Install them with:")
        print("    pip install google-api-python-client google-auth")
        print("\nOr run with --export-csv to generate ready-to-import CSV files instead.")
        sys.exit(1)

    if not os.path.exists(credentials_path):
        print(f"[!] Error: Credentials file not found at: {credentials_path}")
        sys.exit(1)

    print(f"\n[+] Authenticating with Google Cloud Service Account...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)

    # 1. Fetch current spreadsheet info
    print(f"[+] Connecting to Spreadsheet ID: {spreadsheet_id}")
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in spreadsheet.get("sheets", [])}

    requests = []

    # 2. Ensure each tab exists
    for tab_name in schema.get("tabs", {}).keys():
        if tab_name not in existing_sheets:
            print(f"  -> Creating tab: {tab_name}")
            requests.append({
                "addSheet": {
                    "properties": {
                        "title": tab_name,
                        "gridProperties": {
                            "frozenRowCount": 1
                        }
                    }
                }
            })
        else:
            print(f"  -> Tab already exists: {tab_name} (freezing top row)")
            requests.append({
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": existing_sheets[tab_name],
                        "gridProperties": {
                            "frozenRowCount": 1
                        }
                    },
                    "fields": "gridProperties.frozenRowCount"
                }
            })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()

    # 3. Refresh sheet IDs after creation
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id_map = {s["properties"]["title"]: s["properties"]["sheetId"] for s in spreadsheet.get("sheets", [])}

    # 4. Populate Headers and Default Data
    value_updates = []
    format_requests = []

    for tab_name, tab_data in schema.get("tabs", {}).items():
        headers = tab_data.get("headers", [])
        default_data = tab_data.get("default_data", [])
        sheet_id = sheet_id_map[tab_name]

        rows = [headers] + default_data
        value_updates.append({
            "range": f"'{tab_name}'!A1",
            "values": rows
        })

        # Style header row (Bold + Dark Slate Background + White Text)
        format_requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(headers)
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.15, "green": 0.18, "blue": 0.25},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        })

    # Execute Value updates
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": value_updates
        }
    ).execute()

    # Execute Formatting updates
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": format_requests}
    ).execute()

    print("\n[SUCCESS] Google Sheet initialized successfully with 4 styled tabs and default topic pillars!")


def main():
    parser = argparse.ArgumentParser(description="Initialize Google Sheets for Telegram AI Pipeline")
    parser.add_argument("--credentials", "-c", help="Path to Service Account JSON key file")
    parser.add_argument("--sheet-id", "-s", help="Google Spreadsheet ID")
    parser.add_argument("--export-csv", action="store_true", help="Export CSV templates for manual import")
    parser.add_argument("--output-dir", default="./sheets_templates", help="Output directory for CSVs")

    args = parser.parse_args()
    schema = load_schema()

    if args.export_csv or not (args.credentials and args.sheet_id):
        export_csv_templates(schema, Path(args.output_dir))
        return

    init_via_google_api(args.credentials, args.sheet_id, schema)


if __name__ == "__main__":
    main()
