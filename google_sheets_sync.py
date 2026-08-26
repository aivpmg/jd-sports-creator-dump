import os
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID = "1VgC2CvxDxrHF6MWXtLw1JO7skDW9Dpsu1t0bDDeOZM0"

def load_env():
    cwd = os.getcwd()
    env_path = os.path.join(cwd, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip()
                        if val.startswith('"') and val.endswith('"'): val = val[1:-1]
                        elif val.startswith("'") and val.endswith("'"): val = val[1:-1]
                        os.environ[key] = val

def get_sheets_service():
    load_env()
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    return build('sheets', 'v4', credentials=creds)

def sync_creator_to_sheets(details):
    """
    Syncs a single creator's details back to the master Google Sheet.
    If the creator exists (matched by link), updates the row.
    Otherwise, appends a new row.
    """
    service = get_sheets_service()
    if not service:
        print("Google Sheets service not available.")
        return False, "Google credentials not configured."

    market = details.get("market", "UK")
    # Map market to sheet name
    market_map = {
        "UK": "UK",
        "France": "FR",
        "Spain": "ESP",
        "Portugal": "PT",
        "Germany": "DE",
        "Italy": "ITA",
        "Netherlands": "NL"
    }
    sheet_name = market_map.get(market, market)

    try:
        # Fetch sheet metadata to verify sheet exists
        meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_titles = [s['properties']['title'] for s in meta.get('sheets', [])]
        
        if sheet_name not in sheet_titles:
            # If sheet doesn't exist, default to UK or create it
            sheet_name = "UK"

        # Fetch all rows to find if creator exists
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=sheet_name).execute()
        rows = result.get('values', [])
        
        if not rows:
            return False, f"Sheet {sheet_name} is empty."

        header = [col.strip() for col in rows[0]]
        
        # Find column indices
        try:
            name_idx = header.index("Creator Name")
            link_idx = header.index("Link")
            gender_idx = header.index("Gender")
            platform_idx = header.index("Platform")
            worked_idx = header.index("Worked with them?")
            notes_idx = header.index("Notes")
            agency_idx = header.index("Agency")
        except ValueError as e:
            return False, f"Missing standard columns in Google Sheet: {e}"

        brand_columns = ["Campus", "Samba", "Asics", "Shox", "Salomon", "Puma", "Lacoste", "Timberland", "Jordan", "All", "Couple"]
        brand_indices = {b: header.index(b) for b in brand_columns if b in header}

        # Prepare row data
        row_len = len(header)
        new_row = [""] * row_len
        
        new_row[name_idx] = details.get("name", "")
        new_row[link_idx] = details.get("link", "")
        new_row[gender_idx] = details.get("gender", "")
        
        # Platform mapping
        plat = details.get("platform", "Instagram")
        if plat == "Instagram":
            new_row[platform_idx] = "IG"
        elif plat == "TikTok":
            new_row[platform_idx] = "TT"
        elif plat == "YouTube":
            new_row[platform_idx] = "YT"
        else:
            new_row[platform_idx] = plat
            
        new_row[worked_idx] = "TRUE" if details.get("worked_with", 0) == 1 else "FALSE"
        new_row[notes_idx] = details.get("notes", "")
        new_row[agency_idx] = details.get("agency", "")

        # Brand mapping
        brands_str = details.get("brands", "").lower()
        for brand, idx in brand_indices.items():
            if brand.lower() in brands_str:
                new_row[idx] = "TRUE"
            else:
                new_row[idx] = "FALSE"

        # Check if creator already exists in the sheet
        match_row_idx = -1
        for i, r in enumerate(rows[1:], start=2):
            if len(r) > link_idx and r[link_idx].strip().lower() == details.get("link", "").strip().lower():
                match_row_idx = i
                break

        if match_row_idx != -1:
            # Update existing row
            # Preserve any columns we don't manage
            existing_row = rows[match_row_idx - 1]
            for idx, val in enumerate(new_row):
                if val != "":
                    if idx < len(existing_row):
                        existing_row[idx] = val
                    else:
                        existing_row.append(val)
            
            # Pad existing row to match header length
            while len(existing_row) < row_len:
                existing_row.append("")
                
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!A{match_row_idx}",
                valueInputOption="USER_ENTERED",
                body={"values": [existing_row]}
            ).execute()
            return True, f"Updated creator in Google Sheet ({sheet_name})."
        else:
            # Append new row
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [new_row]}
            ).execute()
            return True, f"Appended new creator to Google Sheet ({sheet_name})."

    except Exception as e:
        return False, f"Google Sheets API Error: {e}"
