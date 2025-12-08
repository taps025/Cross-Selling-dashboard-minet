
import streamlit as st
import requests
import pandas as pd
import re
import time

# ✅ Use new deployed API URLs
API_URL = "https://api-6z3n.onrender.com/data"
UPDATE_URL = "https://api-6z3n.onrender.com/update"

# ✅ Canonicalization helper (ONLY affects what we send to API, not your UI)
def canonicalize(name: str) -> str:
    """Remove punctuation and normalize case for API keys."""
    if not isinstance(name, str):
        return ""
    base = re.sub(r"[`\.,:\-]+", "", name)      # strip commas/periods/colons/backticks/dashes
    base = re.sub(r"\s+", " ", base).strip()    # collapse spaces
    return base.upper()

# ✅ Custom CSS (Fix title and logo spacing) — unchanged
st.markdown("""
    <style>
        .block-container {
            padding-top: 2.9rem !important;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        h1 {
            margin-top: 0;
            text-align: center;
        }
        img {
            margin-top: 10px;
        }
        table {
            width: 100% !important;
            border-collapse: collapse;
        }
        .scroll-container {
            max-height: 500px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 5px;
        }
        thead th {
            position: sticky;
            top: 0;
            background-color: #f8f9fa;
            z-index: 2;
        }
    </style>
""", unsafe_allow_html=True)

# ✅ Header Layout — unchanged
col1, col2 = st.columns([2, 8])
with col1:
    st.image("minet.png", width=180)
with col2:
    st.markdown("<h1 style='color:#2C3E50;'>OFFICE OF THE CUSTOMER DASHBOARD</h1>", unsafe_allow_html=True)

# ✅ Fetch data from API (add cache-busting to avoid stale data)
try:
    response = requests.get(
        API_URL,
        params={'_ts': int(time.time())},  # cache buster
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
        timeout=20
    )
    if response.status_code == 200:
        df = pd.DataFrame(response.json())

        # Sidebar Filters — unchanged
        st.sidebar.header("FILTERS")
        sheet_filter = st.sidebar.selectbox("DEPARTMENT", options=df["SOURCE_SHEET"].unique().tolist())
        client_filter = st.sidebar.text_input("CLIENT NAME")

        # ✅ Change Status Filter — unchanged
        st.sidebar.subheader("CHANGE STATUS")
        client_code_input = st.sidebar.text_input("Enter Client Code to Edit")

        # Filter by sheet — unchanged
        filtered_df = df[df["SOURCE_SHEET"] == sheet_filter].copy()
        if client_filter:
            filtered_df = filtered_df[filtered_df["CLIENT NAME"].str.contains(client_filter, case=False, na=False)]

        # ✅ Columns based on sheet — unchanged
        if sheet_filter == "SS":
            columns_to_show = ["CLIENT CODE", "CLIENT NAME", "PREMIUM,", "CORPORATE.", "PERSONAL LINES.", "AFFINITY.", "EMPLOYEE BENEFITS."]
        elif sheet_filter == "corp":
            columns_to_show = ["CLIENT CODE", "CLIENT NAME", "PREMIUM.", "EMPLOYEE BENEFITS", "PERSONAL LINES", "STAFF SCHEMES"]
        elif sheet_filter == "EB":
            columns_to_show = ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE-", "AFFINITY-", "STAFF SCHEMES-", "PERSONAL LINES-"]
        elif sheet_filter == "PLD":
            columns_to_show = ["CLIENT CODE", "CLIENT NAME", "PREMIUM;", "CORPORATE:", "STAFF SCHEMES:", "EMPLOYEE BENEFITS:", "AFFINITY:", "MINING:"]
        elif sheet_filter == "AFFINITY":
            columns_to_show = ["CLIENT CODE", "CLIENT NAME", "PREMIUM:", "EMPLOYEE BENEFITS,", "STAFF SCHEMES,", "PERSONAL LINES,"]
        elif sheet_filter == "MINING":
            columns_to_show = ["CLIENT CODE", "CLIENT NAME", "PREMIUM`", "EMPLOYEE BENEFITS`", "AFFINITY`", "STAFF SCHEMES`", "PERSONAL LINES`"]
        else:
            columns_to_show = filtered_df.columns.tolist()

        available_cols = [col for col in columns_to_show if col in filtered_df.columns]
        display_df = filtered_df[available_cols]

        # ✅ If client code entered, filter case-insensitive — unchanged UI (more robust)
        if client_code_input:
            display_df = display_df[
                display_df["CLIENT CODE"].astype(str).str.strip().str.lower() ==
                (client_code_input or "").strip().lower()
            ]

        # ✅ Format premium columns safely — unchanged visuals
        for col in display_df.columns:
            if "PREMIUM" in col.upper():
                display_df[col] = display_df[col].apply(
                    lambda x: f"{float(x):,.2f}" if pd.notnull(x) and str(x).replace('.', '', 1).isdigit() else str(x)
                )

        # ✅ Highlight "Cross-Sell" — unchanged
        def highlight_cross_sell(val):
            return "color: red; font-weight: bold;" if str(val).strip().lower() == "cross-sell" else ""

        styled_df = display_df.style.applymap(highlight_cross_sell).hide(axis="index")
        st.markdown(f'<div class="scroll-container">{styled_df.to_html()}</div>', unsafe_allow_html=True)

        # ✅ Edit section — UI unchanged; only payload + refresh improved
        if client_code_input:
            if display_df.empty:
                st.warning("No client found with that code.")
            else:
                st.markdown("### Edit Client Details")
                editable_cols = [col for col in display_df.columns if col not in ["CLIENT CODE", "CLIENT NAME"]]
                selected_col = st.selectbox("Select Column to Edit", options=editable_cols)
                new_value_option = st.selectbox("Select New Value", options=["Cross-Sell", "Shared Client"])
                final_value = new_value_option

                if st.button("Apply Change"):
                    # 🔒 Normalize keys sent to API so backend can match reliably
                    payload = {
                        "sheet": canonicalize(sheet_filter),
                        "client_code": (client_code_input or "").strip().upper(),
                        "column": canonicalize(selected_col),
                        "new_value": final_value
                    }
                    try:
                        update_response = requests.post(
                            UPDATE_URL,
                            json=payload,
                            headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
                            timeout=20
                        )
                        if update_response.status_code == 200:
                            st.success(update_response.json().get("message", "Updated successfully."))

                            # 🔄 Force a fresh GET to avoid stale cache after update
                            try:
                                _ = requests.get(
                                    API_URL,
                                    params={'_ts': int(time.time())},
                                    headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
                                    timeout=20
                                )
                            except Exception as e:
                                st.warning(f"Updated, but refresh failed: {e}")

                            st.rerun()
                        else:
                            # Show server message if provided
                            try:
                                st.error(update_response.json().get("message", f"Update failed ({update_response.status_code})."))
                            except Exception:
                                st.error(f"Update failed with status {update_response.status_code}.")
                    except Exception as e:
                        st.error(f"Error updating via API: {e}")

    else:
        st.error("Failed to fetch data from API")
except Exception as e:
    st.error(f"Error connecting to API: {e}")

