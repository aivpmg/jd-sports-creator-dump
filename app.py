import streamlit as st
import sqlite3
import pandas as pd
import os
import re
import subprocess
from creator_extractor import parse_social_link, lookup_creator_in_db, extract_creator_details
from google_sheets_sync import sync_creator_to_sheets

DB_PATH = "creator_dump.db"

# Page configuration
st.set_page_config(
    page_title="JD Sports Creator Dump",
    page_icon="👟",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for a subtle, chic, and professional light pink theme ✨
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* Apply Inter font globally */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #FFFDFD;
    }
    
    /* Main Header Styling */
    .main-header {
        font-size: 3.0rem;
        background: linear-gradient(45deg, #FFB6C1, #DB7093, #E8C5C8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        margin-bottom: 0.1rem;
        text-align: center;
        letter-spacing: -1px;
    }
    
    .sub-header {
        font-size: 1.0rem;
        color: #BC8F8F;
        margin-bottom: 1.0rem;
        text-align: center;
        font-weight: 500;
    }
    
    /* Center the pull button */
    .center-btn {
        display: flex;
        justify-content: center;
        margin-bottom: 2.0rem;
    }
    
    /* Style Streamlit Buttons to be Light Pink & Professional */
    div.stButton > button {
        background: linear-gradient(135deg, #FFB6C1, #DB7093) !important;
        color: white !important;
        border: none !important;
        padding: 0.6rem 2.0rem !important;
        border-radius: 25px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        box-shadow: 0 4px 10px rgba(219, 112, 147, 0.2) !important;
        transition: all 0.3s ease !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 15px rgba(219, 112, 147, 0.3) !important;
        background: linear-gradient(135deg, #DB7093, #FFB6C1) !important;
    }
    
    /* Style Tabs */
    button[data-baseweb="tab"] {
        color: #BC8F8F !important;
        font-weight: 600 !important;
        font-size: 1.0rem !important;
    }
    
    button[aria-selected="true"] {
        color: #DB7093 !important;
        border-bottom-color: #DB7093 !important;
    }
    
    /* Make the table container look gorgeous */
    [data-testid="stElementToolbar"] {
        display: none;
    }
    .stDataFrame {
        border: 1px solid #FFE4E1 !important;
        border-radius: 15px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 12px rgba(219, 112, 147, 0.05) !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions for database operations
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def save_creator(details):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO creators (name, handle, platform, link, gender, market, city, followers, avg_views, worked_with, brands, keywords, vertical, example, sprout_link, notes, agency, shortlisted, added_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        ON CONFLICT(link) DO UPDATE SET
            name = excluded.name,
            handle = excluded.handle,
            platform = excluded.platform,
            gender = excluded.gender,
            market = excluded.market,
            city = excluded.city,
            followers = excluded.followers,
            avg_views = excluded.avg_views,
            worked_with = excluded.worked_with,
            brands = excluded.brands,
            keywords = excluded.keywords,
            vertical = excluded.vertical,
            example = excluded.example,
            sprout_link = excluded.sprout_link,
            notes = excluded.notes,
            agency = excluded.agency,
            added_by = excluded.added_by,
            updated_at = CURRENT_TIMESTAMP
        """, (
            details["name"],
            details["handle"],
            details["platform"],
            details["link"],
            details["gender"],
            details["market"],
            details["city"],
            details["followers"],
            details["avg_views"],
            details["worked_with"],
            details["brands"],
            details["keywords"],
            details["vertical"],
            details.get("example", ""),
            details.get("sprout_link", ""),
            details["notes"],
            details["agency"],
            details.get("added_by", "User")
        ))
        conn.commit()
        
        # Automatically sync back to Google Sheet! 🚀
        success, msg = sync_creator_to_sheets(details)
        if success:
            return True, f"Creator {details['handle']} saved and synced to Google Sheet successfully! ✨"
        else:
            return True, f"Creator {details['handle']} saved locally, but Google Sheet sync failed: {msg}"
            
    except Exception as e:
        return False, f"Error saving creator: {e}"
    finally:
        conn.close()

def delete_creator(creator_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM creators WHERE id = ?", (creator_id,))
        conn.commit()
        return True, "Creator deleted successfully."
    except Exception as e:
        return False, f"Error deleting creator: {e}"
    finally:
        conn.close()

def format_followers(val):
    if not val:
        return "0"
    try:
        val = int(val)
    except ValueError:
        return str(val)
    if val >= 1000000:
        return f"{val / 1000000:.1f}M".replace(".0M", "M")
    elif val >= 1000:
        return f"{int(round(val / 1000))}K"
    return str(val)

# Initialize database if not exists
if not os.path.exists(DB_PATH):
    import import_google_sheets
    import_google_sheets.main()

# Main App Layout with Sparkles! ✨
st.markdown("<div class='main-header'>✨ JD Sports Creator Dump ✨</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>A refined, highly functional shared workspace to filter, shortlist, and manage creators.</div>", unsafe_allow_html=True)

# Center the Pull Latest from Google Sheet Button directly under the title! 🚀
col_btn_space1, col_pull_btn, col_btn_space2 = st.columns([2, 1, 2])
with col_pull_btn:
    pull_btn = st.button("🔄 Pull Latest from Sheet", width="stretch")
    if pull_btn:
        with st.spinner("Pulling latest creators from Google Sheet..."):
            try:
                result = subprocess.run(["python3", "import_google_sheets.py"], capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("Successfully pulled latest creators! ✨")
                    st.rerun()
                else:
                    st.error(f"Failed to pull: {result.stderr}")
            except Exception as e:
                st.error(f"Error: {e}")

# Tabs
tab_search, tab_add, tab_import_export = st.tabs(["🔍 Search & Filter", "➕ Add Creator", "📥 Import & Export"])

# Predefined markets
MARKET_OPTIONS = ["UK", "France", "Spain", "Portugal", "Germany", "Italy", "Netherlands"]
GENDER_OPTIONS = ["Female", "Male", "Couple", "Other", "Unknown"]
PLATFORM_OPTIONS = ["Instagram", "TikTok", "YouTube", "Other"]

# ==========================================
# TAB 1: SEARCH & FILTER
# ==========================================
with tab_search:
    # Search and Filter Controls (Perfectly aligned in a single row!)
    col_search, col_plat, col_gender, col_market, col_brand, col_vert, col_worked = st.columns([2, 1, 1, 1, 1, 1, 1])
    
    with col_search:
        search_query = st.text_input("Search", "", placeholder="Search for creators... ✨")
        
    # Load filter options
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get unique verticals dynamically from the database!
    cursor.execute("SELECT DISTINCT vertical FROM creators WHERE vertical IS NOT NULL AND vertical != ''")
    verticals = sorted([r[0] for r in cursor.fetchall()])
    
    # Get unique brands dynamically from the database!
    cursor.execute("SELECT DISTINCT brands FROM creators WHERE brands IS NOT NULL AND brands != ''")
    all_brands_raw = [r[0] for r in cursor.fetchall()]
    unique_brands = set()
    for b_str in all_brands_raw:
        for b in b_str.split(","):
            unique_brands.add(b.strip())
    brand_options = ["All"] + sorted(list(unique_brands))
    
    conn.close()
    
    with col_plat:
        platform_filter = st.selectbox("Platform", ["All"] + PLATFORM_OPTIONS)
    with col_gender:
        gender_filter = st.selectbox("Gender", ["All"] + GENDER_OPTIONS)
    with col_market:
        market_filter = st.selectbox("Market", ["All"] + MARKET_OPTIONS)
    with col_brand:
        brand_filter = st.selectbox("Brand Fit", brand_options)
    with col_vert:
        vertical_filter = st.selectbox("Vertical", ["All"] + verticals)
    with col_worked:
        worked_filter = st.selectbox("Worked?", ["All", "Yes", "No"])
        
    # Build Query
    query = """
    SELECT id, platform, handle, name, gender, market, city, followers, avg_views, worked_with, brands, keywords, vertical, example, sprout_link, notes, agency, link
    FROM creators
    WHERE 1=1
    """
    params = []
    
    if search_query:
        query += " AND (name LIKE ? OR handle LIKE ? OR city LIKE ? OR notes LIKE ? OR agency LIKE ? OR keywords LIKE ? OR vertical LIKE ?)"
        like_param = f"%{search_query}%"
        params.extend([like_param, like_param, like_param, like_param, like_param, like_param, like_param])
        
    if platform_filter != "All":
        query += " AND platform = ?"
        params.append(platform_filter)
        
    if gender_filter != "All":
        query += " AND gender = ?"
        params.append(gender_filter)
        
    if market_filter != "All":
        # Map full country names to sheet names if needed
        market_map = {
            "UK": "UK",
            "France": "FR",
            "Spain": "ESP",
            "Portugal": "PT",
            "Germany": "DE",
            "Italy": "ITA",
            "Netherlands": "NL"
        }
        mapped_market = market_map.get(market_filter, market_filter)
        query += " AND (market = ? OR market = ?)"
        params.extend([market_filter, mapped_market])
        
    if brand_filter != "All":
        query += " AND brands LIKE ?"
        params.append(f"%{brand_filter}%")
        
    if vertical_filter != "All":
        query += " AND vertical = ?"
        params.append(vertical_filter)
        
    if worked_filter == "Yes":
        query += " AND worked_with = 1"
    elif worked_filter == "No":
        query += " AND worked_with = 0"
        
    query += " ORDER BY followers DESC"
    
    # Load Data
    conn = get_db_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        st.info("No creators found matching the search criteria.")
    else:
        # Format worked_with as boolean for checkbox column
        df["worked_with"] = df["worked_with"].apply(lambda x: True if x == 1 else False)
        
        # Format follower count with K/M
        df["followers_formatted"] = df["followers"].apply(format_followers)
        
        # Prepare DataFrame for display with exactly the requested columns
        display_df = df[["id", "link", "handle", "platform", "name", "followers_formatted", "brands", "keywords", "vertical", "worked_with", "notes", "example", "sprout_link"]].copy()
        # Set handle column to be the link URL if available, otherwise keep handle text
        display_df["handle_link"] = display_df.apply(lambda r: r["link"] if r["link"] else r["handle"], axis=1)
        # Automatically generate Sprout Social link if empty
        display_df["sprout_link_formatted"] = display_df.apply(lambda r: r["sprout_link"] if r["sprout_link"] else f"https://app.taggermedia.com/profile/{r['handle'].replace('@', '')}", axis=1)
        # Reorder columns to match user request exactly
        display_df = display_df[["platform", "handle_link", "name", "followers_formatted", "brands", "keywords", "vertical", "worked_with", "notes", "example", "sprout_link_formatted"]]
        
        st.markdown("### 📝 Interactive Creator Table")
        st.markdown("*Double-click **any cell** in the table to edit directly, then click **Save Table Changes** below!*")
        
        # Display Table with st.data_editor (with hide_index=True!)
        # EVERY SINGLE CELL IS NOW EDITABLE! 🚀
        edited_df = st.data_editor(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "platform": st.column_config.SelectboxColumn("Platform", options=PLATFORM_OPTIONS),
                "handle_link": st.column_config.LinkColumn("Handle", display_text=r"([^/]+)/?$", help="Click to visit social profile"),
                "name": st.column_config.TextColumn("Name"),
                "followers_formatted": st.column_config.TextColumn("Follower Count", help="e.g., 23K, 1.2M"),
                "brands": st.column_config.TextColumn("Brands Fit", help="e.g., Samba, Asics, Salomon"),
                "keywords": st.column_config.TextColumn("Keywords", help="e.g., streetwear, vintage, funny"),
                "vertical": st.column_config.TextColumn("Vertical", help="Type any vertical you want! 💅"),
                "worked_with": st.column_config.CheckboxColumn("Worked with them?"),
                "notes": st.column_config.TextColumn("Notes"),
                "example": st.column_config.LinkColumn("Example", display_text="Example", help="Click to view example post"),
                "sprout_link_formatted": st.column_config.LinkColumn("Sprout Profile", display_text="Sprout Profile", help="Click to view Sprout Social profile")
            },
            key="creator_editor",
            num_rows="fixed"
        )
        
        # Save Table Changes Button
        if st.button("💾 Save Table Changes", type="primary"):
            changes = st.session_state.get("creator_editor", {})
            edited_rows = changes.get("edited_rows", {})
            
            if edited_rows:
                conn = get_db_connection()
                cursor = conn.cursor()
                for index_str, row_changes in edited_rows.items():
                    index = int(index_str)
                    creator_id = int(df.iloc[index]["id"])
                    
                    # Build update query dynamically based on edited fields
                    update_fields = []
                    update_params = []
                    
                    if "platform" in row_changes:
                        update_fields.append("platform = ?")
                        update_params.append(row_changes["platform"])
                        
                    if "handle_link" in row_changes:
                        update_fields.append("link = ?")
                        update_params.append(row_changes["handle_link"])
                        # Extract handle from link
                        plat_norm, handle, _ = parse_social_link(row_changes["handle_link"])
                        update_fields.append("handle = ?")
                        update_params.append(handle)
                        
                    if "name" in row_changes:
                        update_fields.append("name = ?")
                        update_params.append(row_changes["name"])
                        
                    if "followers_formatted" in row_changes:
                        # Parse K/M back to integer
                        f_str = str(row_changes["followers_formatted"]).upper().strip()
                        try:
                            if "M" in f_str:
                                followers = int(float(f_str.replace("M", "")) * 1000000)
                            elif "K" in f_str:
                                followers = int(float(f_str.replace("K", "")) * 1000)
                            else:
                                followers = int(float(f_str.replace(",", "")))
                        except ValueError:
                            followers = 0
                        update_fields.append("followers = ?")
                        update_params.append(followers)
                    
                    if "worked_with" in row_changes:
                        update_fields.append("worked_with = ?")
                        update_params.append(1 if row_changes["worked_with"] else 0)
                        
                    if "notes" in row_changes:
                        update_fields.append("notes = ?")
                        update_params.append(row_changes["notes"])
                        
                    if "brands" in row_changes:
                        update_fields.append("brands = ?")
                        update_params.append(row_changes["brands"])
                        
                    if "keywords" in row_changes:
                        update_fields.append("keywords = ?")
                        update_params.append(row_changes["keywords"])
                        
                    if "vertical" in row_changes:
                        update_fields.append("vertical = ?")
                        update_params.append(row_changes["vertical"])
                        
                    if "example" in row_changes:
                        update_fields.append("example = ?")
                        update_params.append(row_changes["example"])
                        
                    if "sprout_link_formatted" in row_changes:
                        update_fields.append("sprout_link = ?")
                        update_params.append(row_changes["sprout_link_formatted"])
                        
                    if update_fields:
                        update_params.append(creator_id)
                        query = f"UPDATE creators SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                        cursor.execute(query, update_params)
                        
                        # Sync the updated creator back to Google Sheet! 🚀
                        cursor.execute("SELECT * FROM creators WHERE id = ?", (creator_id,))
                        updated_row = cursor.fetchone()
                        sync_creator_to_sheets(dict(updated_row))
                            
                conn.commit()
                conn.close()
                st.success("Changes saved and synced to Google Sheet successfully! ✨")
                st.rerun()
            else:
                st.info("No changes detected in the table.")
                
        # Edit/Delete Section
        st.markdown("---")
        st.subheader("Edit or Delete Creator Details")
        selected_creator_handle = st.selectbox("Select Creator to Edit/Delete", df["handle"].unique())
        
        if selected_creator_handle:
            creator_row = df[df["handle"] == selected_creator_handle].iloc[0]
            
            with st.form(f"edit_form_{creator_row['id']}"):
                col_e1, col_e2, col_e3 = st.columns(3)
                with col_e1:
                    edit_name = st.text_input("Name", creator_row["name"])
                    edit_followers = st.number_input("Followers", value=int(creator_row["followers"]), step=1000)
                    edit_worked_with = st.checkbox("Worked with them? 🤝", value=bool(creator_row["worked_with"]))
                with col_e2:
                    # Map database market to full name if needed
                    db_market = creator_row["market"]
                    market_map_rev = {
                        "UK": "UK",
                        "FR": "France",
                        "ESP": "Spain",
                        "PT": "Portugal",
                        "DE": "Germany",
                        "ITA": "Italy",
                        "NL": "Netherlands"
                    }
                    mapped_db_market = market_map_rev.get(db_market, db_market)
                    edit_market = st.selectbox("Market", MARKET_OPTIONS, index=MARKET_OPTIONS.index(mapped_db_market) if mapped_db_market in MARKET_OPTIONS else 0)
                    edit_views = st.number_input("Average Views", value=int(creator_row["avg_views"]), step=1000)
                    edit_brands = st.text_input("Brands Fit (comma-separated)", creator_row["brands"] or "")
                    edit_keywords = st.text_input("Keywords (comma-separated)", creator_row["keywords"] or "")
                with col_e3:
                    edit_city = st.text_input("City", creator_row["city"] or "Unknown")
                    edit_gender = st.selectbox("Gender", GENDER_OPTIONS, index=GENDER_OPTIONS.index(creator_row["gender"]) if creator_row["gender"] in GENDER_OPTIONS else 0)
                    edit_agency = st.text_input("Agency / Talent Management", creator_row["agency"] or "")
                    edit_vertical = st.text_input("Vertical", creator_row["vertical"] or "Fashion")
                    edit_example = st.text_input("Example Link", creator_row["example"] or "")
                    edit_sprout_link = st.text_input("Sprout Social Link", creator_row["sprout_link"] or "")
                    
                edit_notes = st.text_area("Notes", creator_row["notes"] or "")
                
                col_btn1, col_btn2 = st.columns([1, 5])
                with col_btn1:
                    save_changes = st.form_submit_button("Save Changes")
                with col_btn2:
                    delete_btn = st.form_submit_button("Delete Creator", type="secondary")
                    
                if save_changes:
                    updated_details = {
                        "handle": creator_row["handle"],
                        "name": edit_name,
                        "platform": creator_row["platform"],
                        "link": creator_row["link"],
                        "followers": edit_followers,
                        "avg_views": edit_views,
                        "market": edit_market,
                        "city": edit_city,
                        "gender": edit_gender,
                        "worked_with": 1 if edit_worked_with else 0,
                        "brands": edit_brands,
                        "keywords": edit_keywords,
                        "vertical": edit_vertical,
                        "example": edit_example,
                        "sprout_link": edit_sprout_link,
                        "notes": edit_notes,
                        "agency": edit_agency,
                        "added_by": "User"
                    }
                    success, msg = save_creator(updated_details)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                        
                if delete_btn:
                    success, msg = delete_creator(creator_row["id"])
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

# ==========================================
# TAB 2: ADD CREATOR
# ==========================================
with tab_add:
    st.subheader("Add New Creator")
    st.markdown("Fill in the details below to add a creator manually, or use the **Quick Auto-Fill** tool to fetch details from a link!")
    
    # Quick Auto-Fill Tool
    st.markdown("### ⚡ Quick Auto-Fill from Link")
    col_link, col_btn = st.columns([3, 1])
    with col_link:
        link_input = st.text_input("Social Media Link", placeholder="https://www.instagram.com/username/ or https://www.tiktok.com/@username", key="quick_link_input")
    with col_btn:
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        fetch_btn = st.button("Auto-Fill Form ✨")
        
    # Handle Auto-Fill (Directly updating st.session_state keys for instant pre-filling!)
    if fetch_btn:
        if not link_input:
            st.error("Please enter a link.")
        else:
            with st.spinner("Fetching creator details..."):
                # Check if creator already exists in the database!
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT market, handle FROM creators WHERE link = ? OR handle LIKE ?", (link_input, f"%{link_input.split('/')[-1]}%"))
                existing = cursor.fetchone()
                conn.close()
                
                if existing:
                    st.warning(f"⚠️ Warning: This creator is already in the database under the market: **{existing[0]}**! (Handle: {existing[1]})")
                
                details = extract_creator_details(link_input, None)
                
                # Update session state keys directly
                st.session_state["add_name"] = details["name"]
                st.session_state["add_handle"] = details["handle"]
                st.session_state["add_platform"] = details["platform"]
                st.session_state["add_followers"] = int(details["followers"])
                st.session_state["add_link"] = details["link"]
                st.session_state["add_sprout_link"] = details["sprout_link"]
                st.session_state["add_example"] = details.get("example", "")
                st.session_state["add_notes"] = details["notes"]
                st.session_state["add_market"] = details.get("market", "UK")
                st.session_state["add_city"] = details.get("city", "Unknown")
                st.session_state["add_gender"] = details.get("gender", "Female")
                st.session_state["add_brands"] = details.get("brands", "")
                st.session_state["add_keywords"] = details.get("keywords", "")
                st.session_state["add_vertical"] = details.get("vertical", "Fashion")
                st.session_state["add_agency"] = details.get("agency", "")
                st.session_state["add_worked_with"] = bool(details.get("worked_with", 0))
                
                st.success("Form pre-filled successfully! Review and edit the details below.")
                st.rerun()
                
    # Initialize session state keys if not present
    if "add_name" not in st.session_state:
        st.session_state["add_name"] = ""
    if "add_handle" not in st.session_state:
        st.session_state["add_handle"] = ""
    if "add_platform" not in st.session_state:
        st.session_state["add_platform"] = "Instagram"
    if "add_followers" not in st.session_state:
        st.session_state["add_followers"] = 0
    if "add_link" not in st.session_state:
        st.session_state["add_link"] = ""
    if "add_sprout_link" not in st.session_state:
        st.session_state["add_sprout_link"] = ""
    if "add_example" not in st.session_state:
        st.session_state["add_example"] = ""
    if "add_notes" not in st.session_state:
        st.session_state["add_notes"] = ""
    if "add_market" not in st.session_state:
        st.session_state["add_market"] = "UK"
    if "add_city" not in st.session_state:
        st.session_state["add_city"] = "Unknown"
    if "add_gender" not in st.session_state:
        st.session_state["add_gender"] = "Female"
    if "add_brands" not in st.session_state:
        st.session_state["add_brands"] = ""
    if "add_keywords" not in st.session_state:
        st.session_state["add_keywords"] = ""
    if "add_vertical" not in st.session_state:
        st.session_state["add_vertical"] = "Fashion"
    if "add_agency" not in st.session_state:
        st.session_state["add_agency"] = ""
    if "add_worked_with" not in st.session_state:
        st.session_state["add_worked_with"] = False
    
    st.markdown("---")
    st.markdown("### 📝 Creator Details Form")
    
    with st.form("add_creator_form"):
        # Highly visible Example Link section at the top of the form
        st.markdown("#### 🔗 Example Post Link")
        form_example = st.text_input("Example Link", key="add_example", placeholder="Paste a link to a specific TikTok video or Instagram Reel here... 🎥✨", help="This will be hyperlinked in the main table!")
        
        st.markdown("---")
        
        # Using 4 columns to use up the space as much as possible!
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            form_name = st.text_input("Name", key="add_name")
            form_handle = st.text_input("Handle", key="add_handle")
            form_platform = st.selectbox("Platform", ["Instagram", "TikTok", "YouTube", "Twitter/X", "Facebook", "Other"], key="add_platform")
            form_worked_with = st.checkbox("Worked with them? 🤝", key="add_worked_with")
        with col_f2:
            form_followers = st.number_input("Followers", key="add_followers", step=1000)
            form_link = st.text_input("Profile Link", key="add_link")
            form_brands = st.text_input("Brands Fit (comma-separated)", key="add_brands")
        with col_f3:
            form_keywords = st.text_input("Keywords (comma-separated)", key="add_keywords")
            form_market = st.selectbox("Market", MARKET_OPTIONS, key="add_market")
            form_city = st.text_input("City", key="add_city")
        with col_f4:
            form_gender = st.selectbox("Gender", GENDER_OPTIONS, key="add_gender")
            form_agency = st.text_input("Agency / Talent Management", key="add_agency")
            form_vertical = st.text_input("Vertical", key="add_vertical", placeholder="Type any vertical... 💅")
            form_sprout_link = st.text_input("Sprout Social Link", key="add_sprout_link")
            
        form_notes = st.text_area("Notes", key="add_notes")
        
        save_btn = st.form_submit_button("Save to Creator Dump 💖")
        
        if save_btn:
            if not form_handle or not form_link:
                st.error("Handle and Profile Link are required!")
            else:
                # Check if creator already exists in the database before saving!
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT market FROM creators WHERE link = ?", (form_link,))
                existing = cursor.fetchone()
                conn.close()
                
                if existing:
                    st.error(f"❌ Error: This creator already exists in the database under the market: **{existing[0]}**!")
                else:
                    final_details = {
                        "handle": form_handle,
                        "name": form_name,
                        "platform": form_platform,
                        "link": form_link,
                        "followers": form_followers,
                        "avg_views": int(form_followers * 0.15), # Default average views to 15% of followers
                        "market": form_market,
                        "city": form_city,
                        "gender": form_gender,
                        "worked_with": 1 if form_worked_with else 0,
                        "brands": form_brands,
                        "keywords": form_keywords,
                        "vertical": form_vertical,
                        "example": form_example,
                        "sprout_link": form_sprout_link,
                        "notes": form_notes,
                        "agency": form_agency,
                        "added_by": "User"
                    }
                    success, msg = save_creator(final_details)
                    if success:
                        st.success(msg)
                        # Reset session state keys
                        st.session_state["add_name"] = ""
                        st.session_state["add_handle"] = ""
                        st.session_state["add_platform"] = "Instagram"
                        st.session_state["add_followers"] = 0
                        st.session_state["add_link"] = ""
                        st.session_state["add_sprout_link"] = ""
                        st.session_state["add_example"] = ""
                        st.session_state["add_notes"] = ""
                        st.session_state["add_market"] = "UK"
                        st.session_state["add_city"] = "Unknown"
                        st.session_state["add_gender"] = "Female"
                        st.session_state["add_brands"] = ""
                        st.session_state["add_keywords"] = ""
                        st.session_state["add_vertical"] = "Fashion"
                        st.session_state["add_agency"] = ""
                        st.session_state["add_worked_with"] = False
                        st.rerun()
                    else:
                        st.error(msg)

# ==========================================
# TAB 3: IMPORT & EXPORT
# ==========================================
with tab_import_export:
    st.subheader("Import & Export Creator Data")
    
    col_exp, col_imp = st.columns(2)
    
    with col_exp:
        st.markdown("### Export Data")
        st.markdown("Download the entire creator dump as a CSV file to share with your team or back up your data.")
        
        conn = get_db_connection()
        all_df = pd.read_sql_query("""
        SELECT handle, name, platform, link, gender, market, city, followers, avg_views, worked_with, brands, keywords, vertical, example, sprout_link, notes, agency, added_by, created_at
        FROM creators
        """, conn)
        conn.close()
        
        csv_data = all_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export to CSV",
            data=csv_data,
            file_name="creator_dump_export.csv",
            mime="text/csv"
        )
        
    with col_imp:
        st.markdown("### Sprout Social & Bulk CSV Import")
        st.markdown("Upload a standard CSV or a **Sprout Social Influencer Marketing Creators CSV export** to bulk import creators into the database.")
        
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        if uploaded_file is not None:
            try:
                import_df = pd.read_csv(uploaded_file)
                st.write("Preview of uploaded data:")
                st.dataframe(import_df.head())
                
                if st.button("Bulk Import Creators"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    imported_count = 0
                    for _, row in import_df.iterrows():
                        # Map Sprout Social columns if present, otherwise use standard columns
                        # Sprout Social usually has columns like "Name", "Handle", "Platform", "Followers", "Profile Link", "Email", "Bio"
                        name = str(row.get("Name", row.get("name", ""))).strip()
                        handle = str(row.get("Handle", row.get("handle", ""))).strip()
                        platform = str(row.get("Platform", row.get("platform", "Other"))).strip()
                        link = str(row.get("Profile Link", row.get("Profile URL", row.get("link", "")))).strip()
                        followers_val = row.get("Followers", row.get("followers", 0))
                        
                        # Clean followers
                        try:
                            followers = int(float(str(followers_val).replace(",", "").replace(" ", "")))
                        except ValueError:
                            followers = 0
                            
                        gender = str(row.get("Gender", row.get("gender", "Unknown"))).strip()
                        market = str(row.get("Country", row.get("market", "Unknown"))).strip()
                        city = str(row.get("City", row.get("city", "Unknown"))).strip()
                        worked_with = int(row.get("worked_with", 0))
                        brands = str(row.get("brands", "")).strip()
                        keywords = str(row.get("keywords", "")).strip()
                        vertical = str(row.get("vertical", "Fashion")).strip()
                        example = str(row.get("example", "")).strip()
                        sprout_link = str(row.get("sprout_link", row.get("Sprout Link", ""))).strip()
                        notes = str(row.get("notes", "")).strip()
                        agency = str(row.get("agency", "")).strip()
                        
                        if not link:
                            # Try to construct link from handle and platform
                            if handle:
                                if platform.lower() in ["ig", "instagram"]:
                                    link = f"https://www.instagram.com/{handle.replace('@', '')}/"
                                elif platform.lower() in ["tt", "tiktok"]:
                                    link = f"https://www.tiktok.com/@{handle.replace('@', '')}"
                                else:
                                    continue
                            else:
                                continue
                                
                        if not handle:
                            # Extract handle from link
                            platform_norm, handle, _ = parse_social_link(link)
                            
                        # Insert or update creator
                        cursor.execute("""
                        INSERT INTO creators (handle, name, platform, link, gender, market, city, followers, avg_views, worked_with, brands, keywords, vertical, example, sprout_link, notes, agency, shortlisted, added_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'Bulk Import')
                        ON CONFLICT(link) DO UPDATE SET
                            handle = excluded.handle,
                            name = excluded.name,
                            platform = excluded.platform,
                            gender = excluded.gender,
                            market = excluded.market,
                            city = excluded.city,
                            followers = excluded.followers,
                            avg_views = excluded.avg_views,
                            worked_with = excluded.worked_with,
                            brands = excluded.brands,
                            keywords = excluded.keywords,
                            vertical = excluded.vertical,
                            example = excluded.example,
                            sprout_link = excluded.sprout_link,
                            notes = excluded.notes,
                            agency = excluded.agency,
                            updated_at = CURRENT_TIMESTAMP
                        """, (handle, name, platform, link, gender, market, city, followers, 0, worked_with, brands, keywords, vertical, example, sprout_link, notes, agency))
                        imported_count += 1
                        
                    conn.commit()
                    conn.close()
                    st.success(f"Successfully imported {imported_count} creators! ✨")
                    st.rerun()
            except Exception as e:
                st.error(f"Error importing data: {e}")
