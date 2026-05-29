"""
NJ Flood Ordinance Viewer
Reads classified JSON files from public Google Drive folder
No API key needed — uses direct download links
"""

import streamlit as st
import json
import re
import html
import requests
from pathlib import Path
from collections import defaultdict

st.set_page_config(
    page_title="NJ Flood Ordinance Viewer",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #f5f7fa; }
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e4ea;
    }
    .main-header {
        background: linear-gradient(135deg, #1a3a5c 0%, #2563a8 100%) !important;
        color: white !important;
        padding: 28px 32px;
        border-radius: 12px;
        margin-bottom: 24px;
    }
    .main-header h1 {
        font-family: 'Georgia', serif;
        font-size: 26px;
        font-weight: 700;
        color: white !important;
        margin: 0 0 6px 0;
    }
    .main-header p {
        font-size: 14px;
        color: white !important;
        opacity: 0.85;
        margin: 0;
    }
    [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e0e4ea !important;
        border-radius: 6px !important;
        margin-top: 8px !important;
    }
    [data-testid="stExpander"] summary {
        color: #2563a8 !important;
        font-size: 13px !important;
        font-weight: 600 !important;
    }
    .section-card {
        background: white;
        border: 1px solid #e0e4ea;
        border-left: 4px solid #2563a8;
        border-radius: 8px;
        padding: 20px 24px;
        margin-bottom: 4px;
    }
    .section-ref {
        font-size: 13px;
        font-weight: 700;
        color: #2563a8 !important;
        font-family: 'Courier New', monospace;
        background: #eff6ff;
        padding: 2px 8px;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 8px;
    }
    .section-title {
        font-size: 17px;
        font-weight: 600;
        color: #111827 !important;
        font-family: 'Georgia', serif;
        margin-bottom: 8px;
    }
    .chapter-tag {
        font-size: 11px;
        background: #f0f4ff;
        color: #3730a3 !important;
        border: 1px solid #c7d2fe;
        border-radius: 12px;
        padding: 3px 10px;
        margin-right: 6px;
        display: inline-block;
    }
    .page-tag {
        font-size: 11px;
        background: #f3f4f6;
        color: #4b5563 !important;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 3px 10px;
        display: inline-block;
    }
    .reason-tag {
        font-size: 12px;
        color: #059669 !important;
        background: #ecfdf5;
        border: 1px solid #d1fae5;
        border-radius: 4px;
        padding: 5px 12px;
        display: inline-block;
        margin-top: 8px;
    }
    .section-text {
        font-size: 13px !important;
        line-height: 1.8 !important;
        color: #374151 !important;
        font-family: 'Georgia', serif !important;
        white-space: pre-wrap;
        word-wrap: break-word;
        background-color: #f9fafb !important;
        padding: 16px !important;
        border-radius: 6px !important;
        border: 1px solid #e5e7eb !important;
    }
    .section-text * {
        font-family: 'Georgia', serif !important;
        color: #374151 !important;
        background: transparent !important;
        font-size: 13px !important;
    }
    .no-results {
        background: white;
        border: 1px dashed #d1d5db;
        border-radius: 10px;
        padding: 48px;
        text-align: center;
        color: #9ca3af;
    }
    .sidebar-label {
        font-size: 11px;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 6px;
    }
    .town-meta {
        font-size: 13px;
        color: #6b7280;
        margin-bottom: 20px;
    }
    .flood-count {
        font-size: 14px;
        color: #1a3a5c;
        font-weight: 600;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ── Config ──
# Paste your Google Drive folder ID here
GDRIVE_FOLDER_ID = "https://drive.google.com/drive/u/1/folders/1aZ54i0JnvOXIh1n2_7Vv15g0WoM9CbFT"

DEFAULT_COUNTY = "Atlantic County"
DEFAULT_TOWN   = "Town of Hammonton"


def get_gdrive_files(folder_id):
    """
    List all files in a public Google Drive folder.
    Uses the simple export URL — no API key needed.
    """
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    # Use Google Drive API v3 public endpoint
    api_url = (
        f"https://www.googleapis.com/drive/v3/files"
        f"?q='{folder_id}'+in+parents"
        f"&fields=files(id,name)"
        f"&pageSize=1000"
        f"&key={st.secrets.get('GDRIVE_API_KEY', '')}"
    )
    resp = requests.get(api_url, timeout=30)
    if resp.status_code != 200:
        return []
    return resp.json().get("files", [])


def download_json_file(file_id):
    """Download a single JSON file from Google Drive by file ID."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    resp = requests.get(url, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return None


@st.cache_data(show_spinner=False)
def load_all_towns_gdrive(folder_id):
    """Load all JSON files from public Google Drive folder."""
    files = get_gdrive_files(folder_id)
    if not files:
        return {}, {}

    county_town_map = defaultdict(list)
    all_data = {}

    progress = st.progress(0, text="Loading towns...")
    json_files = [f for f in files if f["name"].endswith(".json")]

    for idx, file in enumerate(json_files):
        try:
            data = download_json_file(file["id"])
            if not data:
                continue
            town   = data.get("town",   file["name"])
            county = data.get("county", "Unknown County")
            county_town_map[county].append((town, file["id"]))
            all_data[file["id"]] = data
            progress.progress(
                (idx + 1) / len(json_files),
                text=f"Loading {town}..."
            )
        except Exception:
            continue

    progress.empty()
    for county in county_town_map:
        county_town_map[county].sort(key=lambda x: x[0])

    return dict(county_town_map), all_data


@st.cache_data(show_spinner=False)
def load_all_towns_local(folder="./data/classified"):
    """Fallback: load from local folder."""
    p = Path(folder)
    if not p.exists():
        return {}, {}

    county_town_map = defaultdict(list)
    all_data = {}

    for json_file in sorted(p.glob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
            town   = data.get("town",   json_file.stem)
            county = data.get("county", "Unknown County")
            county_town_map[county].append((town, str(json_file)))
            all_data[str(json_file)] = data
        except Exception:
            continue

    for county in county_town_map:
        county_town_map[county].sort(key=lambda x: x[0])

    return dict(county_town_map), all_data


@st.cache_data
def get_flood_sections(key, _all_data):
    data     = _all_data.get(key, {})
    sections = data.get("sections", [])
    flood = [
        s for s in sections
        if s.get("flood_related") is True
        and not s.get("is_toc_entry", False)
    ]
    def sort_key(s):
        m = re.search(r"(\d+)-(\d+)", s.get("section_ref", ""))
        return (int(m.group(1)), int(m.group(2))) if m else (9999, 9999)
    return sorted(flood, key=sort_key)


# ── Load data ──
if GDRIVE_FOLDER_ID != "YOUR_FOLDER_ID_HERE":
    with st.spinner("Loading ordinance data..."):
        county_town_map, all_data = load_all_towns_gdrive(GDRIVE_FOLDER_ID)
else:
    county_town_map, all_data = load_all_towns_local()


# ── Sidebar ──
with st.sidebar:
    st.markdown("### 🌊 NJ Flood Ordinances")
    st.markdown("---")

    if not county_town_map:
        st.error("No data found. Check your Google Drive folder ID.")
        st.stop()

    counties           = sorted(county_town_map.keys())
    default_county_idx = counties.index(DEFAULT_COUNTY) if DEFAULT_COUNTY in counties else 0

    st.markdown('<div class="sidebar-label">County</div>', unsafe_allow_html=True)
    selected_county = st.selectbox(
        "County", counties,
        index=default_county_idx,
        label_visibility="collapsed"
    )

    towns_in_county  = county_town_map.get(selected_county, [])
    town_names       = [t[0] for t in towns_in_county]
    default_town_idx = town_names.index(DEFAULT_TOWN) if DEFAULT_TOWN in town_names else 0

    st.markdown('<div class="sidebar-label">Town</div>', unsafe_allow_html=True)
    selected_town = st.selectbox(
        "Town", town_names,
        index=default_town_idx,
        label_visibility="collapsed"
    )

    selected_key = next(
        (t[1] for t in towns_in_county if t[0] == selected_town), None
    )


# ── Main panel ──
st.markdown(f"""
<div class="main-header">
    <h1>🌊 NJ Flood Ordinance Viewer</h1>
    <p>{len(county_town_map)} counties · {sum(len(v) for v in county_town_map.values())} towns</p>
</div>
""", unsafe_allow_html=True)

if not selected_key:
    st.info("Select a county and town from the sidebar.")
    st.stop()

data           = all_data.get(selected_key, {})
flood_sections = get_flood_sections(selected_key, all_data)

st.markdown(f"## {selected_town}")
st.markdown(
    f'<div class="town-meta">'
    f'{selected_county} &nbsp;·&nbsp; '
    f'{data.get("pdf_name", "")} &nbsp;·&nbsp; '
    f'{data.get("total_pages", 0)} pages'
    f'</div>',
    unsafe_allow_html=True
)
st.markdown(
    f'<div class="flood-count">🌊 {len(flood_sections)} flood-related sections found</div>',
    unsafe_allow_html=True
)

if not flood_sections:
    st.markdown("""
    <div class="no-results">
        <div style="font-size:32px;margin-bottom:12px">🔍</div>
        <div style="font-size:16px;font-weight:600;color:#4b5563">
            No flood-related sections found for this town
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.markdown("---")

for sec in flood_sections:
    ref     = sec.get("section_ref", "")
    title   = sec.get("section_title", "")
    chapter = sec.get("chapter", "")
    ps      = sec.get("page_start", "?")
    pe      = sec.get("page_end", "?")
    reason  = sec.get("classification_reason", "")
    text    = sec.get("full_text", "")

    st.markdown(f"""
<div class="section-card">
    <div><span class="section-ref">{html.escape(ref)}</span></div>
    <div class="section-title">{html.escape(title)}</div>
    <div>
        <span class="chapter-tag">{html.escape(chapter)}</span>
        <span class="page-tag">pp. {ps}–{pe}</span>
    </div>
    {f'<div class="reason-tag">✓ {html.escape(reason)}</div>' if reason else ''}
</div>
""", unsafe_allow_html=True)

    with st.expander("📄 Read full text"):
        st.markdown(
            f'<div class="section-text">{html.escape(text)}</div>',
            unsafe_allow_html=True
        )

st.markdown("---")
st.markdown(
    f'<div style="font-size:12px;color:#9ca3af;text-align:center">'
    f'Showing {len(flood_sections)} flood-related sections · '
    f'{selected_town} · {selected_county}'
    f'</div>',
    unsafe_allow_html=True
)
