# app2.py
# ------------------------------------------------------------
# Engagements viewer (dependent on main app)
# ------------------------------------------------------------
import streamlit as st
import pandas as pd
from pathlib import Path

# CONFIG
ENGAGEMENTS_LOCAL_CSV = "engagement_tracker.csv"
TITLE_FONT_SIZE_REM = 10.0
LOGO_WIDTH_PX = 150
DUE_SOON_DAYS = 7

st.set_page_config(page_title="CROSS-SELLING ENGAGEMENT TRACKER", layout="wide")

# Logo helper
def find_logo(candidate_name: str = "minet.png"):
    candidates = []
    cwd = Path.cwd()
    candidates += [cwd / candidate_name, cwd / "images" / candidate_name]
    try:
        script_dir = Path(__file__).parent
    except NameError:
        script_dir = None
    if script_dir:
        candidates += [
            script_dir / candidate_name,
            script_dir.parent / candidate_name,
            script_dir / "images" / candidate_name,
        ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None

# Header
def render_header_inline(title_text: str):
    st.markdown(
        f"""
        <style>
        .header-title {{
            font-size: {TITLE_FONT_SIZE_REM}rem;
            font-weight: bold;
            line-height: 1.1;
            margin: 10;
        }}
        .header-block {{
            margin-bottom: 0.5rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container():
        col_logo, col_title = st.columns([1, 6], vertical_alignment="center")
        with col_logo:
            logo_path = find_logo("minet.png")
            if logo_path:
                st.image(str(logo_path), width=LOGO_WIDTH_PX)
            else:
                st.empty()
        with col_title:
            st.markdown(
                f"<div class='header-block'><h2 class='header-title'>{title_text}</h2></div>",
                unsafe_allow_html=True,
            )

# Data helpers
def normalize_engagement_df(df_e: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "ID", "Client Name", "Facilitator", "Facilitator Email",
        "Date", "Type", "Notes", "Status", "Flag", "Reminder Sent At",
    ]
    if df_e.empty:
        return pd.DataFrame(columns=cols)
    df_e = df_e.rename(columns={
        "id": "ID",
        "client_name": "Client Name",
        "facilitator": "Facilitator",
        "facilitator_email": "Facilitator Email",
        "date": "Date",  # internal name stays "Date"
        "type": "Type",
        "notes": "Notes",
        "status": "Status",
        "flag": "Flag",
        "reminder_sent_at": "Reminder Sent At",
    })
    for c in cols:
        if c not in df_e.columns:
            df_e[c] = ""
    def parse_date(x):
        if pd.isna(x) or str(x).strip() == "":
            return ""
        try:
            # keep a standard ISO for internal use
            return pd.to_datetime(str(x)).date().isoformat()
        except Exception:
            return str(x)
    df_e["Date"] = df_e["Date"].apply(parse_date)
    df_e["Status"] = df_e["Status"].replace("", "Open")
    return df_e[cols]

def load_engagements() -> pd.DataFrame:
    csv_script = (Path(__file__).parent / ENGAGEMENTS_LOCAL_CSV) if "__file__" in globals() else None
    csv_cwd = Path.cwd() / ENGAGEMENTS_LOCAL_CSV
    for p in [csv_script, csv_cwd]:
        if p and p.exists():
            try:
                return normalize_engagement_df(pd.read_csv(p))
            except Exception as e:
                st.error(f"Failed to read {p}: {e}")
                return normalize_engagement_df(pd.DataFrame())
    return normalize_engagement_df(pd.DataFrame())

# Flag logic
def compute_flags(df_in: pd.DataFrame) -> pd.DataFrame:
    df = df_in.copy()
    today = pd.Timestamp.today().normalize()
    dt = pd.to_datetime(df["Date"], errors="coerce")
    status_lower = df["Status"].astype(str).str.lower()
    is_closed = status_lower == "closed"
    is_open = ~is_closed
    has_date = dt.notna()
    df["Flag"] = ""
    df.loc[is_closed, "Flag"] = "Actioned"
    delta_days = (dt - today).dt.days
    df.loc[is_open & has_date & (delta_days < 0), "Flag"] = "Late"
    df.loc[is_open & has_date & (delta_days == 0), "Flag"] = "Due soon"
    df.loc[is_open & has_date & (delta_days > 0) & (delta_days <= DUE_SOON_DAYS), "Flag"] = "Due soon"
    df.loc[is_open & has_date & (delta_days > DUE_SOON_DAYS), "Flag"] = "Upcoming"
    return df


# Styling
def style_flags(df_in: pd.DataFrame, show_cols: list[str]):
    def flag_style(val: str) -> str:
        v = (val or "").strip().lower()
        if v.startswith("late"): return "background-color:#dc2626;color:white;font-weight:600;"
        if v.startswith("due soon"): return "background-color:#f59e0b;color:black;font-weight:600;"
        if v.startswith("actioned"): return "background-color:#16a34a;color:white;font-weight:600;"
        if v.startswith("upcoming"): return "background-color:#93c5fd;color:black;font-weight:600;"
        return ""
    return df_in[show_cols].style.applymap(flag_style, subset=["Flag"])

# UI
render_header_inline("CROSS-SELLING ENGAGEMENT TRACKER")
df = load_engagements()
if df.empty:
    st.info("No engagement entries found yet.")
    st.stop()

df = compute_flags(df)

# Build month range from internal "Date"
date_parsed = pd.to_datetime(df["Date"], errors="coerce")
min_date = date_parsed.min()
max_date = date_parsed.max()
if pd.isna(min_date) or pd.isna(max_date):
    base = pd.Timestamp.today().normalize().replace(day=1)
    min_date = base
    max_date = base

start_period = min_date.to_period("M")
end_period = max_date.to_period("M")
all_periods = pd.period_range(start=start_period, end=end_period, freq="M")

def month_label(p: pd.Period) -> str:
    return p.to_timestamp().strftime("%B %Y")

month_labels = [month_label(p) for p in all_periods]
label_to_period = {month_label(p): p for p in all_periods}

# Sidebar filters
st.sidebar.header("FILTERS")
facilitators = sorted([f for f in df["Facilitator"].dropna().unique().tolist() if str(f).strip() != ""])
facilitator_sel = st.sidebar.selectbox("Facilitator", options=["(All)"] + facilitators, index=0)
status_options = ["Open", "Closed"]
status_sel = st.sidebar.multiselect("Status", options=status_options, default=status_options)
months_sel = st.sidebar.multiselect("Months", options=month_labels, default=month_labels)

# Apply filters
df_view = df.copy()
if facilitator_sel and facilitator_sel != "(All)":
    df_view = df_view[df_view["Facilitator"] == facilitator_sel]
if status_sel and len(status_sel) > 0:
    df_view = df_view[df_view["Status"].isin(status_sel)]

df_view["_month_period"] = pd.to_datetime(df_view["Date"], errors="coerce").dt.to_period("M")
if months_sel and len(months_sel) > 0:
    selected_periods = {label_to_period[m] for m in months_sel if m in label_to_period}
    df_view = df_view[df_view["_month_period"].isin(selected_periods)]

# Sort by internal Date descending
if "Date" in df_view.columns:
    with pd.option_context("mode.chained_assignment", None):
        df_view["_DateParsed"] = pd.to_datetime(df_view["Date"], errors="coerce")
        df_view = df_view.sort_values(by="_DateParsed", ascending=False).drop(columns=["_DateParsed"])
df_view = df_view.drop(columns=["_month_period"], errors="ignore")

# --- Presentation layer ---
# 1) Rename column header for the UI
df_display = df_view.rename(columns={"Date": "Date of cross-sell engagement"})

# 2) Format date values as "DD Month YYYY" (e.g., 16 December 2025)
with pd.option_context("mode.chained_assignment", None):
    date_series = pd.to_datetime(df_display["Date of cross-sell engagement"], errors="coerce")
    # Format: Day (2-digit), Full Month Name, Year
    df_display["Date of cross-sell engagement"] = date_series.dt.strftime("%d %B %Y")
    # For rows with invalid/blank dates, keep as empty string
    df_display["Date of cross-sell engagement"] = df_display["Date of cross-sell engagement"].fillna("")

fixed_cols_in_order = [
    "Facilitator", "Client Name", "Date of cross-sell engagement", "Type", "Notes", "Status", "Flag",
]
available_cols = [c for c in fixed_cols_in_order if c in df_display.columns]

if df_display.empty or not available_cols:
    st.info("No engagements available to display.")
else:
    styled = style_flags(df_display, available_cols)
    st.markdown(styled.to_html(), unsafe_allow_html=True)

