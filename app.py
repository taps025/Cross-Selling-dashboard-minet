
import streamlit as st
import requests
import pandas as pd
import time
import re

# ===== API endpoints =====
API_URL = "https://api-6z3n.onrender.com/data"
UPDATE_URL = "https://api-6z3n.onrender.com/update"

# ===== Helpers =====
def canonicalize(name: str) -> str:
    """Normalize names: remove punctuation/backticks/commas/periods/colons/dashes, normalize whitespace, upper-case."""
    if not isinstance(name, str):
        return ""
    base = re.sub(r"[`\.,:\-]+", "", name)
    base = re.sub(r"\s+", " ", base).strip()
    return base.upper()

def fetch_data():
    """GET with cache busting + no-cache headers."""
    return requests.get(
        API_URL,
        params={"_ts": int(time.time())},
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        timeout=15
    )

def find_column(df: pd.DataFrame, target_names):
    """
    Find the best matching column in df given a list of possible display names.
    We canonicalize both df columns and targets, then map back to the original col.
    """
    if df is None or df.empty:
        return None
    # Map canonical -> original col (first occurrence wins)
    norm_map = {}
    for c in df.columns:
        norm_map.setdefault(canonicalize(c), c)

    # Accept either a list or a single string
    if isinstance(target_names, str):
        target_names = [target_names]

    for t in target_names:
        ct = canonicalize(t)
        if ct in norm_map:
            return norm_map[ct]
    return None

def safe_columns(df: pd.DataFrame, desired_columns):
    """Return actual df columns matching desired (by normalization). Fallback to all df columns if none found."""
    actual = []
    for d in desired_columns:
        col = find_column(df, d)
        if col:
            actual.append(col)
    if not actual:
        # If nothing matched, show all columns so the table isn't empty
        actual = list(df.columns)
    return actual

# ===== UI (CSS) =====
st.markdown("""
<style>
    .block-container { padding-top: 2.9rem !important; padding-left: 1rem; padding-right: 1rem; max-width: 100%; }
    h1 { margin-top: 0; text-align: center; }
    img { margin-top: 10px; }
    table { width: 100% !important; border-collapse: collapse; }
    .scroll-container { max-height: 500px; overflow-y: auto; border: 1px solid #ddd; padding: 5px; }
    thead th { position: sticky; top: 0; background-color: #f8f9fa; z-index: 2; }
</style>
""", unsafe_allow_html=True)

# ===== Header =====
col1, col2 = st.columns([2, 8])
with col1:
    st.image("minet.png", width=180)
with col2:
    st.markdown("<h1 style='color:#2C3E50;'>OFFICE OF THE CUSTOMER DASHBOARD</h1>", unsafe_allow_html=True)

# ===== Data fetch with diagnostics =====
try:
    resp = fetch_data()
    st.caption(f"API status: {resp.status_code}")
    if resp.status_code == 200:
        try:
            raw = resp.json()
        except Exception as e:
            st.error(f"Failed to parse JSON: {e}")
            st.stop()

        # Convert to DataFrame, handle list/dict responses safely
        if isinstance(raw, list):
            df = pd.DataFrame(raw)
        elif isinstance(raw, dict) and "data" in raw:
            df = pd.DataFrame(raw["data"])
        else:
            # Show raw to help diagnose structure
            st.warning("Unexpected JSON structure. Showing raw response below.")
            st.write(raw)
            st.stop()

        st.caption(f"Rows: {len(df)}, Columns: {len(df.columns)}")
        if not df.empty:
            st.caption("Sample:")
            st.dataframe(df.head(5))
        else:
            st.warning("No data returned from API. Please check the /data endpoint.")
            st.stop()

        # ===== Sidebar Filters =====
        st.sidebar.header("FILTERS")

        # Resolve SOURCE_SHEET safely
        sheet_col = find_column(df, ["SOURCE_SHEET", "SOURCE SHEET", "DEPARTMENT", "SHEET"])
        if sheet_col is None:
            st.error("Could not find the sheet/department column (e.g., 'SOURCE_SHEET').")
            st.write("Available columns:", list(df.columns))
            st.stop()

        sheets = sorted(df[sheet_col].dropna().astype(str).unique().tolist())
        if not sheets:
            st.warning("No sheet values found.")
            st.stop()

        sheet_filter = st.sidebar.selectbox("DEPARTMENT", options=sheets)
        client_filter = st.sidebar.text_input("CLIENT NAME")

        st.sidebar.subheader("CHANGE STATUS")
        client_code_input = st.sidebar.text_input("Enter Client Code to Edit")

        # Filter by sheet
        filtered_df = df[df[sheet_col].astype(str) == str(sheet_filter)].copy()
        if filtered_df.empty:
            st.info("No rows for the selected sheet. Try another DEPARTMENT.")
            st.stop()

        # Resolve CLIENT NAME and CLIENT CODE safely
        client_name_col = find_column(filtered_df, ["CLIENT NAME", "CLIENT", "NAME"])
        client_code_col = find_column(filtered_df, ["CLIENT CODE", "CODE", "CLIENT_ID", "CLIENT ID"])

        # Client name filter
        if client_filter and client_name_col:
            filtered_df = filtered_df[
                filtered_df[client_name_col].astype(str).str.contains(client_filter, case=False, na=False)
            ]

        # ===== Determine columns to show per sheet, robust via normalization =====
        if str(sheet_filter).upper() == "SS":
            desired = ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE", "PERSONAL LINES", "AFFINITY", "EMPLOYEE BENEFITS"]
        elif str(sheet_filter).upper() == "CORP":
            desired = ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "EMPLOYEE BENEFITS", "PERSONAL LINES", "STAFF SCHEMES"]
        elif str(sheet_filter).upper() == "EB":
            desired = ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE", "AFFINITY", "STAFF SCHEMES", "PERSONAL LINES"]
        elif str(sheet_filter).upper() == "PLD":
            desired = ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE", "STAFF SCHEMES", "EMPLOYEE BENEFITS", "AFFINITY", "MINING"]
        elif str(sheet_filter).upper() == "AFFINITY":
            desired = ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "EMPLOYEE BENEFITS", "STAFF SCHEMES", "PERSONAL LINES"]
        elif str(sheet_filter).upper() == "MINING":
            desired = ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "EMPLOYEE BENEFITS", "AFFINITY", "STAFF SCHEMES", "PERSONAL LINES"]
        else:
            desired = list(filtered_df.columns)  # unknown sheet, show all

        show_cols = safe_columns(filtered_df, desired)
        display_df = filtered_df[show_cols]

        # Filter by client code (case-insensitive, trimmed)
        if client_code_input and client_code_col:
            code_key = client_code_input.strip().lower()
            display_df = display_df[
                filtered_df[client_code_col].astype(str).str.strip().str.lower() == code_key
            ]

        # Format premiums only for display (match any col whose canonical name is PREMIUM)
        def is_premium_col(col):
            return canonicalize(col) == "PREMIUM"

        for col in display_df.columns:
            if is_premium_col(col):
                display_df[col] = display_df[col].apply(
                    lambda x: f"{float(x):,.2f}" if pd.notnull(x) and str(x).replace(".", "", 1).isdigit() else str(x)
                )

        # Highlight Cross-Sell
        def highlight_cross_sell(val):
            return "color: red; font-weight: bold;" if str(val).strip().lower() == "cross-sell" else ""

        try:
            styled_df = display_df.style.applymap(highlight_cross_sell).hide(axis="index")
            st.markdown(f'<div class="scroll-container">{styled_df.to_html()}</div>', unsafe_allow_html=True)
        except Exception:
            # For older pandas where .hide may not exist
            styled_df = display_df.style.applymap(highlight_cross_sell)
            st.markdown(f'<div class="scroll-container">{styled_df.to_html()}</div>', unsafe_allow_html=True)

        # ===== Edit section =====
        if client_code_input:
            if display_df.empty:
                st.warning("No client found with that code.")
            else:
                st.markdown("### Edit Client Details")

                # Editable = columns excluding code/name, but resolve dynamically
                excluded = set([c for c in [client_code_col, client_name_col] if c])
                editable_cols = [c for c in display_df.columns if c not in excluded]
                selected_col_display = st.selectbox("Select Column to Edit", options=editable_cols)
                new_value_option = st.selectbox("Select New Value", options=["Cross-Sell", "Shared Client"])
                final_value = new_value_option

                if st.button("Apply Change"):
                    payload = {
                        "sheet": canonicalize(sheet_filter),              # normalize sheet name for API
                        "client_code": client_code_input.strip().upper(), # normalize client code
                        "column": canonicalize(selected_col_display),     # normalize target column for API
                        "new_value": final_value
                    }
                    try:
                        upd = requests.post(
                            UPDATE_URL, json=payload,
                            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
                            timeout=15
                        )
                        if upd.status_code == 200:
                            st.success(upd.json().get("message", "Updated."))
                            # Force refetch to verify
                            refreshed = fetch_data()
                            st.caption(f"Refresh after update: {refreshed.status_code}")
                            if refreshed.status_code == 200:
                                df2 = pd.DataFrame(refreshed.json()) if isinstance(refreshed.json(), list) else pd.DataFrame(refreshed.json().get("data", []))
                                st.caption(f"Rows after update: {len(df2)}")
                            st.rerun()
                        else:
                            # Show server message if any
                            try:
                                st.error(upd.json().get("message", f"Update failed ({upd.status_code})."))
                            except Exception:
                                st.error(f"Update failed with status {upd.status_code}.")
                    except Exception as e:
                        st.error(f"Error updating via API: {e}")
    else:
        st.error("Failed to fetch data from API")
except Exception as e:
    st.error(f"Error connecting to API: {e}")
