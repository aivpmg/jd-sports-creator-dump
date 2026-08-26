#!/usr/bin/env python3
import os
import sys
import sqlite3
import re
import csv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

DB_PATH = "creator_dump.db"
CSV_PATH = "sheet_ORGANIC_Results_By_Creator.csv"

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

def clean_int(val):
    if not val:
        return 0
    val_str = str(val).strip().replace(',', '').replace(' ', '').replace('$', '')
    if not val_str or val_str.lower() in ['n/a', '-', '']:
        return 0
    try:
        return int(float(val_str))
    except ValueError:
        return 0

def extract_handle(link, platform):
    if not link:
        return ""
    link = link.strip().lower()
    if "tiktok.com" in link:
        match = re.search(r'@([a-zA-Z0-9._-]+)', link)
        if match:
            return f"@{match.group(1)}"
    elif "instagram.com" in link:
        # e.g., https://www.instagram.com/username/
        match = re.search(r'instagram\.com/([a-zA-Z0-9._-]+)', link)
        if match:
            return f"@{match.group(1)}"
    elif "youtube.com" in link:
        match = re.search(r'youtube\.com/@([a-zA-Z0-9._-]+)', link)
        if match:
            return f"@{match.group(1)}"
        match = re.search(r'youtube\.com/c/([a-zA-Z0-9._-]+)', link)
        if match:
            return match.group(1)
        match = re.search(r'youtube\.com/user/([a-zA-Z0-9._-]+)', link)
        if match:
            return match.group(1)
    return ""

def normalize_link(link):
    if not link:
        return ""
    link = link.strip().lower()
    link = re.sub(r'^https?://(www\.)?', '', link)
    link = link.rstrip('/')
    return link

def load_organic_metrics():
    """Load follower and view metrics from the organic results CSV."""
    metrics = {}
    if not os.path.exists(CSV_PATH):
        print(f"Organic CSV {CSV_PATH} not found. Skipping metric enrichment.")
        return metrics

    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading organic CSV: {e}")
        return metrics

    if len(rows) < 8:
        return metrics

    header_row = rows[7]
    data_rows = rows[8:]

    try:
        ig_followers_idx = header_row.index("IG FOLLOWERS")
        ig_username_idx = header_row.index("IG USERNAME")
        ig_reels_views_idx = header_row.index("IG REELS LATEST ACHIEVED PLAYS")
        
        tt_link_idx = header_row.index("TT VIDEO LINK")
        tt_followers_idx = header_row.index("TT FOLLOWERS")
        tt_views_idx = header_row.index("TT LATEST ACHIEVED IMPRESSIONS")
        
        yt_link_idx = header_row.index("YT LIVE URL")
        yt_subs_idx = header_row.index("YT CHANNEL SUBS")
        yt_views_idx = header_row.index("YT VID VIEWS")
    except ValueError as e:
        print(f"Error finding column indices in organic CSV: {e}")
        return metrics

    for row in data_rows:
        # Instagram
        ig_username = row[ig_username_idx].strip() if len(row) > ig_username_idx else ""
        if ig_username:
            norm_link = normalize_link(f"https://www.instagram.com/{ig_username}")
            followers = clean_int(row[ig_followers_idx]) if len(row) > ig_followers_idx else 0
            views = clean_int(row[ig_reels_views_idx]) if len(row) > ig_reels_views_idx else 0
            metrics[norm_link] = {"followers": followers, "views": views}

        # TikTok
        tt_link = row[tt_link_idx].strip() if len(row) > tt_link_idx else ""
        if tt_link and "tiktok.com" in tt_link:
            match = re.search(r'@([a-zA-Z0-9._-]+)', tt_link)
            if match:
                tt_username = match.group(1)
                norm_link = normalize_link(f"https://www.tiktok.com/@{tt_username}")
                followers = clean_int(row[tt_followers_idx]) if len(row) > tt_followers_idx else 0
                views = clean_int(row[tt_views_idx]) if len(row) > tt_views_idx else 0
                metrics[norm_link] = {"followers": followers, "views": views}

        # YouTube
        yt_link = row[yt_link_idx].strip() if len(row) > yt_link_idx else ""
        if yt_link:
            norm_link = normalize_link(yt_link)
            followers = clean_int(row[yt_subs_idx]) if len(row) > yt_subs_idx else 0
            views = clean_int(row[yt_views_idx]) if len(row) > yt_views_idx else 0
            metrics[norm_link] = {"followers": followers, "views": views}

    return metrics

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drop old tables to start fresh with the pure creator dump schema
    cursor.execute("DROP TABLE IF EXISTS creators")
    cursor.execute("DROP TABLE IF EXISTS campaigns")
    
    # Create creators table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS creators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        handle TEXT,
        platform TEXT,
        link TEXT UNIQUE NOT NULL,
        gender TEXT,
        market TEXT,
        city TEXT,
        followers INTEGER DEFAULT 0,
        avg_views INTEGER DEFAULT 0,
        worked_with INTEGER DEFAULT 0,
        brands TEXT,
        keywords TEXT DEFAULT '',
        vertical TEXT DEFAULT 'Fashion',
        example TEXT DEFAULT '',
        sprout_link TEXT DEFAULT '',
        notes TEXT,
        agency TEXT,
        shortlisted INTEGER DEFAULT 0,
        added_by TEXT DEFAULT 'System',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()
    print("Database schema initialized successfully.")

def main():
    load_env()
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        print("Error: Missing Google credentials.")
        sys.exit(1)

    # Initialize database schema
    init_db()

    # Load organic metrics for enrichment
    organic_metrics = load_organic_metrics()
    print(f"Loaded {len(organic_metrics)} organic creator metrics for enrichment.")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    service = build('sheets', 'v4', credentials=creds)
    spreadsheet_id = "1VgC2CvxDxrHF6MWXtLw1JO7skDW9Dpsu1t0bDDeOZM0"
    
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get('sheets', [])
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    brand_columns = ["Campus", "Samba", "Asics", "Shox", "Salomon", "Puma", "Lacoste", "Timberland", "Jordan", "All", "Couple"]
    
    total_imported = 0
    
    for s in sheets:
        sheet_name = s['properties']['title']
        print(f"Processing sheet: {sheet_name}...")
        
        try:
            result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=sheet_name).execute()
            values = result.get('values', [])
        except Exception as e:
            print(f"Error fetching sheet {sheet_name}: {e}")
            continue
            
        if not values:
            print(f"No data in sheet {sheet_name}.")
            continue
            
        header = [col.strip() for col in values[0]]
        
        # Find column indices (making them optional)
        name_idx = header.index("Creator Name") if "Creator Name" in header else -1
        link_idx = header.index("Link") if "Link" in header else -1
        gender_idx = header.index("Gender") if "Gender" in header else -1
        platform_idx = header.index("Platform") if "Platform" in header else -1
        worked_idx = header.index("Worked with them?") if "Worked with them?" in header else -1
        notes_idx = header.index("Notes") if "Notes" in header else -1
        agency_idx = header.index("Agency") if "Agency" in header else -1
        
        if link_idx == -1:
            print(f"Skipping sheet {sheet_name} because it has no 'Link' column.")
            continue
            
        # Find brand column indices
        brand_indices = {}
        for brand in brand_columns:
            if brand in header:
                brand_indices[brand] = header.index(brand)
                
        sheet_imported = 0
        for row in values[1:]:
            if len(row) <= link_idx:
                continue
                
            link = row[link_idx].strip()
            if not link or link.lower() in ["", "link"]:
                continue
                
            name = row[name_idx].strip() if (name_idx != -1 and len(row) > name_idx) else ""
            gender = row[gender_idx].strip() if (gender_idx != -1 and len(row) > gender_idx) else ""
            platform = row[platform_idx].strip() if (platform_idx != -1 and len(row) > platform_idx) else ""
            
            # Worked with them?
            worked_val = row[worked_idx].strip().upper() if (worked_idx != -1 and len(row) > worked_idx) else "FALSE"
            worked_with = 1 if worked_val == "TRUE" else 0
            
            notes = row[notes_idx].strip() if (notes_idx != -1 and len(row) > notes_idx) else ""
            agency = row[agency_idx].strip() if (agency_idx != -1 and len(row) > agency_idx) else ""
            
            # Extract brands
            brands_list = []
            for brand, idx in brand_indices.items():
                if len(row) > idx:
                    val = row[idx].strip().upper()
                    if val == "TRUE":
                        brands_list.append(brand)
            brands_str = ", ".join(brands_list)
            
            # Extract handle
            handle = extract_handle(link, platform)
            if not handle:
                handle = name if name else "Creator"
                
            # Normalize platform name
            if platform.upper() in ["TT", "TIKTOK"]:
                platform_norm = "TikTok"
            elif platform.upper() in ["IG", "INSTAGRAM"]:
                platform_norm = "Instagram"
            elif platform.upper() in ["YT", "YOUTUBE"]:
                platform_norm = "YouTube"
            else:
                # Try to guess platform from link
                if "tiktok.com" in link.lower():
                    platform_norm = "TikTok"
                elif "instagram.com" in link.lower():
                    platform_norm = "Instagram"
                elif "youtube.com" in link.lower() or "youtu.be" in link.lower():
                    platform_norm = "YouTube"
                else:
                    platform_norm = "Instagram"
                    
            if not name:
                name = handle.replace("@", "")
                
            # Enrich with organic metrics if available
            norm_link = normalize_link(link)
            followers = 0
            avg_views = 0
            if norm_link in organic_metrics:
                followers = organic_metrics[norm_link]["followers"]
                avg_views = organic_metrics[norm_link]["views"]
            else:
                # Try matching by handle
                handle_norm = handle.lower().replace("@", "")
                for ol, m in organic_metrics.items():
                    if handle_norm in ol:
                        followers = m["followers"]
                        avg_views = m["views"]
                        break
            
            # Insert or update
            try:
                cursor.execute("""
                INSERT INTO creators (name, handle, platform, link, gender, market, worked_with, brands, notes, agency, followers, avg_views, keywords, vertical, example, sprout_link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, handle, platform_norm, link, gender, sheet_name, worked_with, brands_str, notes, agency, followers, avg_views, "", "Fashion", "", ""))
                sheet_imported += 1
                total_imported += 1
            except sqlite3.IntegrityError:
                # Update existing
                cursor.execute("""
                UPDATE creators
                SET name = ?, handle = ?, platform = ?, gender = ?, market = ?, worked_with = ?, brands = ?, notes = ?, agency = ?,
                    followers = CASE WHEN ? > 0 THEN ? ELSE followers END,
                    avg_views = CASE WHEN ? > 0 THEN ? ELSE avg_views END
                WHERE link = ?
                """, (name, handle, platform_norm, gender, sheet_name, worked_with, brands_str, notes, agency, followers, followers, avg_views, avg_views, link))
                sheet_imported += 1
                total_imported += 1
                
        print(f"Imported {sheet_imported} creators from sheet {sheet_name}.")
        
    conn.commit()
    conn.close()
    print(f"\nSuccessfully imported a total of {total_imported} creators into the database.")

if __name__ == '__main__':
    main()
