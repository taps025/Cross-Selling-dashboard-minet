
import streamlit as st
import requests
import pandas as pd
import re
import time
import os
import base64
from datetime import date

# ------------------------------
# PAGE CONFIG
# ------------------------------
st.set_page_config(page_title="Office of the Customer Dashboard", layout="wide")

# ------------------------------
# CONFIG
# ------------------------------
API_URL = "https://api-minet.onrender.com/data"          # main data
UPDATE_URL = "https://api-minet.onrender.com/update"      # update endpoint for table edits

# Engagement tracker endpoints (optional; if None -> local CSV persistence)
ENGAGEMENTS_URL = None          # e.g., "https://api-minet.onrender.com/engagements"
ENGAGEMENTS_ADD_URL = None      # e.g., "https://api-minet.onrender.com/engagements/add"
ENGAGEMENTS_UPDATE_URL = None   # e.g., "https://api-minet.onrender.com/engagements/update"
ENGAGEMENTS_LOCAL_CSV = "engagement_tracker.csv"

# ------------------------------
# ROUTING via st.query_params
# ------------------------------
params = st.query_params
route_param = params.get("route", None)
if route_param is None:
    route = st.session_state.get("_route", "dashboard")
else:
    # supports both str and list values
    route = route_param if isinstance(route_param, str) else (
        route_param[0] if isinstance(route_param, list) and route_param else "dashboard"
    )
st.session_state["_route"] = route

def go_to(route_name: str):
    """Navigate by setting URL query params and rerunning (main flow-safe)."""
    st.session_state["_route"] = route_name
    st.query_params.update({"route": route_name})  # update URL
    st.rerun()  # called from main flow

def go_home():
    """Clear route and go back to dashboard (main flow-safe)."""
    st.session_state["_route"] = "dashboard"
    st.query_params.clear()  # remove query params
    st.rerun()  # called from main flow

# ------------------------------
# HELPERS
# ------------------------------
def canonicalize(name: str) -> str:
    """Normalize names for matching in Excel/API."""
    if not isinstance(name, str):
        return ""
    base = re.sub(r"[`\.,:\-\[\]]+", "", name)  # strip punctuation we often see in sheets
    base = re.sub(r"\s+", " ", base).strip()
    return base.upper()

def embed_image_base64(image_path: str) -> str:
    """Return a data URI for an image, or empty string if not found."""
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as f:
        data = f.read()
    lower = image_path.lower()
    if lower.endswith(".png"):
        mime = "image/png"
    elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
        mime = "image/jpeg"
    else:
        mime = "image/png"
    b64 = base64.b64encode(data).decode("utf-8")
    return "data:" + mime + ";base64," + b64

# ---- Engagement Tracker I/O (local-first with optional API) ----
def normalize_engagement_df(df_e: pd.DataFrame) -> pd.DataFrame:
    """Ensure standard columns and types for engagement tracker."""
    cols = [
        "ID", "Client Name", "Facilitator", "Facilitator Email",
        "Date", "Type", "Notes", "Status", "Reminder Sent At"
    ]
    if df_e.empty:
        return pd.DataFrame(columns=cols)

    rename_map = {
        "id": "ID",
        "client_name": "Client Name",
        "facilitator": "Facilitator",
        "facilitator_email": "Facilitator Email",
        "date": "Date",
        "type": "Type",
        "notes": "Notes",
        "status": "Status",
        "reminder_sent_at": "Reminder Sent At",
    }
    df_e = df_e.rename(columns=rename_map)

    for c in cols:
        if c not in df_e.columns:
            df_e[c] = ""

    def fmt_date(x):
        if pd.isna(x) or str(x).strip() == "":
            return ""
        try:
            return pd.to_datetime(str(x)).date().isoformat()
        except Exception:
            return str(x)

    df_e["Date"] = df_e["Date"].apply(fmt_date)
    df_e["Status"] = df_e["Status"].replace("", "Open")
    return df_e[cols]

def load_engagements() -> pd.DataFrame:
    """Load engagements from remote API if configured, else from local CSV."""
    if ENGAGEMENTS_URL:
        try:
            r = requests.get(ENGAGEMENTS_URL, params={'_ts': int(time.time())}, timeout=20)
            if r.status_code == 200:
                return normalize_engagement_df(pd.DataFrame(r.json()))
        except Exception:
            pass

    if os.path.exists(ENGAGEMENTS_LOCAL_CSV):
        try:
            return normalize_engagement_df(pd.read_csv(ENGAGEMENTS_LOCAL_CSV))
        except Exception:
            pass

    return normalize_engagement_df(pd.DataFrame())

def save_engagement(client_name: str, facilitator: str, facilitator_email: str, dt: date, etype: str, notes: str) -> bool:
    """Save engagement via remote API if configured; else append to local CSV."""
    new_id = "E-" + str(int(time.time() * 1000))  # simple unique ID
    payload = {
        "id": new_id,
        "client_name": client_name,
        "facilitator": facilitator,
        "facilitator_email": facilitator_email or "",
        "date": pd.to_datetime(dt).date().isoformat() if dt else "",
        "type": etype or "",
        "notes": notes or "",
        "status": "Open",
    }

    if ENGAGEMENTS_ADD_URL:
        try:
            r = requests.post(ENGAGEMENTS_ADD_URL, json=payload, timeout=20)
            return r.status_code == 200
        except Exception:
            pass

    # Local CSV persistence
    df_e = load_engagements()
    new_row = {
        "ID": payload["id"],
        "Client Name": payload["client_name"],
        "Facilitator": payload["facilitator"],
        "Facilitator Email": payload["facilitator_email"],
        "Date": payload["date"],
        "Type": payload["type"],
        "Notes": payload["notes"],
        "Status": payload["status"],
        "Reminder Sent At": "",
    }
    df_e = pd.concat([df_e, pd.DataFrame([new_row])], ignore_index=True)
    df_e.to_csv(ENGAGEMENTS_LOCAL_CSV, index=False)
    return True

def update_engagement_status(eng_id: str, new_status: str) -> bool:
    """Update status by ID."""
    if ENGAGEMENTS_UPDATE_URL:
        try:
            r = requests.post(ENGAGEMENTS_UPDATE_URL, json={"id": eng_id, "status": new_status}, timeout=20)
            return r.status_code == 200
        except Exception:
            pass

    # Local
    df_e = load_engagements()
    if df_e.empty:
        return False
    idx = df_e.index[df_e["ID"] == eng_id]
    if len(idx) == 0:
        return False
    df_e.loc[idx, "Status"] = new_status
    df_e.to_csv(ENGAGEMENTS_LOCAL_CSV, index=False)
    return True

# ------------------------------
# CSS (responsive + dark-safe + logo-safe)
# ------------------------------
CSS = '''
<style>
  .block-container {
    padding-top: 2.0rem !important;
    padding-left: 0.75rem;
    padding-right: 0.75rem;
    max-width: 100%;
  }
  .header-row {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
  }
  .logo-wrap { padding: 6px 8px; overflow: visible !important; }
  .logo-wrap img { display: block; max-height: 64px; width: auto; height: auto; object-fit: contain; }
  .app-title { margin: 0; line-height: 1.1; font-weight: 800; font-size: 1.9rem; color: #1f2937; text-align: left; letter-spacing: 0.02em; }
  @media (prefers-color-scheme: dark) { .app-title { color: #f3f4f6; } }
  .stApp[data-theme="dark"] .app-title { color: #f3f4f6 !important; }
  .scroll-container {
    max-height: 60vh; overflow-y: auto; overflow-x: auto; border: 1px solid #ddd; padding: 8px; border-radius: 8px; background: transparent;
  }
  .scroll-container table { width: 100%; border-collapse: collapse; table-layout: auto; font-size: 0.92rem; }
  .scroll-container table thead th {
    position: sticky; top: 0; z-index: 2; background-color: #f8f9fa; color: #1f2937; border-bottom: 1px solid #e5e7eb;
    text-transform: uppercase; letter-spacing: 0.02em; font-weight: 700; white-space: normal; padding: 10px 12px;
  }
  .scroll-container table tbody td {
    color: inherit; padding: 10px 12px; vertical-align: top; word-wrap: break-word; white-space: normal; border-bottom: 1px solid #eee;
  }
  @media (prefers-color-scheme: dark) {
    .scroll-container { border-color: #374151; }
    .scroll-container table thead th { background-color: #1f2937; color: #f3f4f6; border-bottom: 1px solid #374151; }
    .scroll-container::-webkit-scrollbar { width: 10px; height: 10px; }
    .scroll-container::-webkit-scrollbar-thumb { background-color: #4b5563; border-radius: 6px; }
    .scroll-container::-webkit-scrollbar-track { background-color: #1f2937; }
  }
  .stApp[data-theme="dark"] .scroll-container table thead th { background-color: #1f2937 !important; color: #f3f4f6 !important; border-bottom: 1px solid #374151 !important; }
  @media (min-width: 600px) {
    .scroll-container table tbody td:first-child, .scroll-container table thead th:first-child {
      position: sticky; left: 0; background-clip: padding-box; background-color: inherit;
    }
  }
  @media (max-width: 480px) {
    .logo-wrap img { max-height: 48px; }
    .app-title { font-size: 1.45rem; }
    .scroll-container { max-height: 65vh; }
    .scroll-container table { font-size: 0.86rem; }
    .scroll-container table thead th, .scroll-container table tbody td { padding: 8px 10px; }
  }
</style>
'''
st.markdown(CSS, unsafe_allow_html=True)

# ------------------------------
# HEADER (embedded logo)
# ------------------------------
logo_path = "minet.png"  # ensure this file exists next to app.py (or change path)
logo_data_uri = embed_image_base64(logo_path)

def render_header(title_text: str):
    if logo_data_uri:
        header_html = (
            '<div class="header-row">'
            '<div class="logo-wrap"><img src="' + logo_data_uri + '" alt="Minet logo"></div>'
            '<h1 class="app-title">' + title_text + '</h1>'
            '</div>'
        )
    else:
        header_html = '<h1 class="app-title">' + title_text + '</h1>'
    st.markdown(header_html, unsafe_allow_html=True)

# ------------------------------
# LOAD DATA FROM API (for dashboard and engagement dropdown)
# ------------------------------
def load_main_data() -> pd.DataFrame:
    try:
        response = requests.get(
            API_URL,
            params={'_ts': int(time.time())},
            headers={'Cache-Control': 'no-cache'},
            timeout=20
        )
        if response.status_code == 200:
            return pd.DataFrame(response.json())
        else:
            st.error("Failed to fetch data from API.")
            return pd.DataFrame()
    except Exception as e:
        st.error("Error connecting to API: " + str(e))
        return pd.DataFrame()

df = load_main_data()

# ------------------------------
# SHARED SIDEBAR (adds Go to filter)
# ------------------------------
def render_sidebar(route_current: str, df_for_options: pd.DataFrame):
    st.sidebar.header("FILTERS")
    # "Go to" filter to switch views
    page_choice = st.sidebar.selectbox(
        "Go to",
        options=["Dashboard", "Engagements"],
        index=0 if route_current == "dashboard" else 1,
        help="Switch between the dashboard and the Engagement Tracker page."
    )
    if page_choice == "Engagements" and route_current != "engagement":
        go_to("engagement")  # main flow call -> st.rerun works
    elif page_choice == "Dashboard" and route_current != "dashboard":
        go_to("dashboard")   # main flow call -> st.rerun works

    # Standard filters (kept visible on both pages for consistency)
    sheet_options = df_for_options["SOURCE_SHEET"].unique().tolist() if not df_for_options.empty else []
    sheet_filter = st.sidebar.selectbox("DEPARTMENT", options=sheet_options) if sheet_options else ""
    client_filter = st.sidebar.text_input("CLIENT NAME")
    client_code_input = st.sidebar.text_input("Enter Client Code to Change Status")
    return sheet_filter, client_filter, client_code_input

# ------------------------------
# DASHBOARD VIEW
# ------------------------------
def render_dashboard(df: pd.DataFrame):
    render_header("OFFICE OF THE CUSTOMER DASHBOARD")
    sheet_filter, client_filter, client_code_input = render_sidebar("dashboard", df)

    # Filter data
    filtered_df = df[df["SOURCE_SHEET"] == sheet_filter].copy() if not df.empty and sheet_filter else pd.DataFrame()
    if not filtered_df.empty and client_filter:
        filtered_df = filtered_df[
            filtered_df["CLIENT NAME"].str.contains(client_filter, case=False, na=False)
        ]

    # Select columns based on sheet
    column_map = {
        "SS": ["CLIENT CODE", "CLIENT NAME", "PREMIUM,", "CORPORATE.", "PERSONAL LINES.", "AFFINITY.", "EMPLOYEE BENEFITS."],
        "corp": ["CLIENT CODE", "CLIENT NAME", "PREMIUM.", "EMPLOYEE BENEFITS", "PERSONAL LINES", "STAFF SCHEMES"],
        "EB": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE-", "AFFINITY-", "STAFF SCHEMES-", "PERSONAL LINES-"],
        "PLD": ["CLIENT CODE", "CLIENT NAME", "PREMIUM;", "CORPORATE:", "STAFF SCHEMES:", "EMPLOYEE BENEFITS:", "AFFINITY:", "MINING:"],
        "AFFINITY": ["CLIENT CODE", "CLIENT NAME", "PREMIUM:", "EMPLOYEE BENEFITS,", "STAFF SCHEMES,", "PERSONAL LINES,"],
        "MINING": ["CLIENT CODE", "CLIENT NAME", "PREMIUM`", "EMPLOYEE BENEFITS`", "AFFINITY`", "STAFF SCHEMES`", "PERSONAL LINES`"]
    }
    columns_to_show = column_map.get(sheet_filter, filtered_df.columns.tolist() if not filtered_df.empty else [])
    available_cols = [c for c in columns_to_show if not filtered_df.empty and c in filtered_df.columns]
    display_df = filtered_df[available_cols].copy() if not filtered_df.empty else pd.DataFrame()

    # Filter by client code
    if not display_df.empty and client_code_input:
        display_df = display_df[
            display_df["CLIENT CODE"].astype(str).str.strip().str.lower() ==
            client_code_input.strip().lower()
        ].copy()

    # Format premium columns
    if not display_df.empty:
        for col in display_df.columns:
            if "PREMIUM" in col.upper():
                display_df.loc[:, col] = display_df[col].apply(
                    lambda x: (
                        f"{float(x):,.2f}"
                        if pd.notnull(x) and str(x).replace('.', '', 1).isdigit()
                        else x
                    )
                )

    # Display table
    def highlight_cross_sell(val):
        return "color: red; font-weight: bold;" if str(val).strip().lower() == "cross-sell" else ""

    if not display_df.empty:
        styled_df = display_df.style.applymap(highlight_cross_sell).hide(axis="index")
        st.markdown('<div class="scroll-container">' + styled_df.to_html() + '</div>', unsafe_allow_html=True)
    else:
        st.info("No data for the current filters.")

    # Edit section (as-is)
    if client_code_input:
        if display_df.empty:
            st.warning("No client found with that code.")
        else:
            st.markdown("### Edit Client Details")
            editable_cols = [c for c in display_df.columns if c not in ["CLIENT CODE", "CLIENT NAME"]]
            selected_col = st.selectbox("Select Column to Edit", options=editable_cols)
            new_value = st.selectbox("Select New Value", options=["Cross-Sell", "Shared Client"])
            if st.button("Apply Change"):
                payload = {
                    "sheet": sheet_filter,
                    "client_code": client_code_input.strip(),
                    "column": selected_col,
                    "new_value": new_value
                }
                try:
                    update_response = requests.post(
                        UPDATE_URL,
                        json=payload,
                        headers={'Cache-Control': 'no-cache'},
                        timeout=20
                    )
                    if update_response.status_code == 200:
                        st.success(update_response.json().get("message", "Updated successfully."))
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(update_response.json().get("message", "Update failed."))
                except Exception as e:
                    st.error("Error updating API: " + str(e))

# ------------------------------
# ENGAGEMENT VIEW (Inputs + Editable Status; ID hidden)
# ------------------------------
def render_engagement(df_for_clients: pd.DataFrame):
    render_header("Engagement Tracker")
    # Sidebar remains (for navigation only; we ignore its filters here)
    _sheet_filter, _client_filter, _client_code_input = render_sidebar("engagement", df_for_clients)

    # Client options from main data (autocomplete)
    client_options = sorted(df_for_clients["CLIENT NAME"].dropna().unique().tolist()) if not df_for_clients.empty else []

    # --- Add Engagement form ---
    with st.form(key="engagement_form", clear_on_submit=True):
        st.markdown("### Add Engagement")
        c1, c2 = st.columns(2)
        with c1:
            client_name = st.selectbox("Client Name", options=client_options, index=None, placeholder="Select client...")
            facilitator = st.text_input("Facilitator", value="")
            dtype = st.selectbox("Engagement Type (optional)", options=["", "Call", "Meeting", "Presentation", "Site Visit", "Other"])
        with c2:
            dt = st.date_input("Date of Engagement", value=date.today())
            facilitator_email = st.text_input("Facilitator Email (optional)", value="")
            notes = st.text_area("Notes (optional)", value="", height=120)
        submitted = st.form_submit_button("Save Engagement")

        if submitted:
            if not client_name:
                st.error("Please select a Client Name.")
            elif not facilitator.strip():
                st.error("Please enter a Facilitator.")
            else:
                ok = save_engagement(
                    client_name=client_name,
                    facilitator=facilitator.strip(),
                    facilitator_email=facilitator_email.strip(),
                    dt=dt,
                    etype=dtype,
                    notes=notes
                )
                if ok:
                    st.success("Engagement saved.")
                    st.rerun()
                else:
                    st.error("Could not save engagement. Please try again.")

    # --- Load data (for table + inline status edits) ---
    eng_df = load_engagements()
    if eng_df.empty:
        st.info("No engagement entries yet.")
        # IMPORTANT: Use main-flow button pattern (no on_click) -> prevents 'no-op' banner
        if st.button("⬅️ Back to Dashboard", type="secondary"):
            go_home()
        return

    # ---------- Engagements Table with inline Status edit (ID hidden) ----------
    st.markdown("### Engagements")

    # Ensure consistent column order / presence
    cols_all = ["ID", "Facilitator", "Client Name", "Date", "Type", "Notes", "Status"]
    for c in cols_all:
        if c not in eng_df.columns:
            eng_df[c] = ""

    # Format date consistently
    def _fmt_date(x):
        if pd.isna(x) or str(x).strip() == "":
            return ""
        try:
            return pd.to_datetime(str(x)).date().isoformat()
        except Exception:
            return str(x)

    eng_df["Date"] = eng_df["Date"].apply(_fmt_date)

    # Build the table WITHOUT the ID column (use ID as index for change detection)
    display_cols = ["Facilitator", "Client Name", "Date", "Type", "Notes", "Status"]  # no "ID"
    table_df = eng_df[["ID"] + display_cols].copy().set_index("ID")

    # Configure columns: Status editable as dropdown, others read-only
    column_config = {
        "Status": st.column_config.SelectboxColumn(
            "Status",
            options=["Open", "Closed"],
            help="Change status, then click 'Apply Changes' to save"
        ),
        "Facilitator": st.column_config.Column("Facilitator", disabled=True),
        "Client Name": st.column_config.Column("Client Name", disabled=True),
        "Date": st.column_config.Column("Date", disabled=True),
        "Type": st.column_config.Column("Type", disabled=True),
        "Notes": st.column_config.Column("Notes", disabled=True),
    }

    edited_df = st.data_editor(
        table_df,
        use_container_width=True,
        hide_index=True,        # hides the ID index from UI
        column_config=column_config
    )

    # Detect and apply Status changes (compare by index = ID)
    st.markdown("#### Apply Changes")
    if st.button("Apply Changes"):
        original_status = table_df[["Status"]].rename(columns={"Status": "Status_original"})
        merged = edited_df.join(original_status, how="left")
        changed = merged[merged["Status"] != merged["Status_original"]]

        if changed.empty:
            st.info("No status changes detected.")
        else:
            successes = 0
            failures = []
            for row_id, row in changed.iterrows():
                ok = update_engagement_status(str(row_id), str(row["Status"]))
                if ok:
                    successes += 1
                else:
                    failures.append(str(row_id))

            if successes:
                st.success(f"Updated status for {successes} engagement(s).")
            if failures:
                st.error(f"Failed to update status for IDs: {', '.join(failures)}")

            # Refresh to show latest values from storage
            time.sleep(0.5)
            st.rerun()

    # IMPORTANT: Use main-flow button pattern (no on_click) -> prevents 'no-op' banner
    if st.button("⬅️ Back to Dashboard", type="secondary"):
        go_home()

# ------------------------------
# RENDER BASED ON ROUTE
# ------------------------------
df = load_main_data()
if route == "engagement":
    render_engagement(df)
else:
    render_dashboard(df)



