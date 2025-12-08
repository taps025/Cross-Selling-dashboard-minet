
import streamlit as st
import requests
import pandas as pd
import time
import re

API_URL = "https://api-6z3n.onrender.com/data"
UPDATE_URL = "https://api-6z3n.onrender.com/update"

def canonicalize(name: str) -> str:
    if not isinstance(name, str):
        return name
    base = re.sub(r"[`\.,:-]+", "", name)            # strip punctuation
    base = re.sub(r"\s+", " ", base).strip()          # normalize spaces
    return base.upper()                               # unify case

# ===== Fetch data (NO CACHE) =====
def fetch_data():
    return requests.get(
        API_URL,
        params={'_ts': int(time.time())},
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
    )

try:
    response = fetch_data()
    if response.status_code == 200:
        df = pd.DataFrame(response.json())

        # Sidebar
        st.sidebar.header("FILTERS")
        sheet_filter = st.sidebar.selectbox("DEPARTMENT", options=sorted(df["SOURCE_SHEET"].dropna().unique().tolist()))
        client_filter = st.sidebar.text_input("CLIENT NAME")

        st.sidebar.subheader("CHANGE STATUS")
        client_code_input = st.sidebar.text_input("Enter Client Code to Edit")

        filtered_df = df[df["SOURCE_SHEET"] == sheet_filter].copy()
        if client_filter:
            filtered_df = filtered_df[filtered_df["CLIENT NAME"].str.contains(client_filter, case=False, na=False)]

        # Choose columns based on sheet (unchanged)
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

        if client_code_input:
            code_key = client_code_input.strip().lower()
            display_df = display_df[display_df["CLIENT CODE"].astype(str).str.strip().str.lower() == code_key]

        # Format premiums (display only)
        for col in display_df.columns:
            if "PREMIUM" in col.upper():
                display_df[col] = display_df[col].apply(
                    lambda x: f"{float(x):,.2f}" if pd.notnull(x) and str(x).replace('.', '', 1).isdigit() else str(x)
                )

        def highlight_cross_sell(val):
            return "color: red; font-weight: bold;" if str(val).strip().lower() == "cross-sell" else ""

        styled_df = display_df.style.applymap(highlight_cross_sell).hide(axis="index")
        st.markdown(f'<div class="scroll-container">{styled_df.to_html()}</div>', unsafe_allow_html=True)

        # Edit section
        if client_code_input:
            if display_df.empty:
                st.warning("No client found with that code.")
            else:
                st.markdown("### Edit Client Details")
                editable_cols = [col for col in display_df.columns if col not in ["CLIENT CODE", "CLIENT NAME"]]
                selected_col_display = st.selectbox("Select Column to Edit", options=editable_cols)
                new_value_option = st.selectbox("Select New Value", options=["Cross-Sell", "Shared Client"])
                final_value = new_value_option

                if st.button("Apply Change"):
                    payload = {
                        "sheet": canonicalize(sheet_filter),                    # normalize sheet name
                        "client_code": client_code_input.strip().upper(),       # normalize client code
                        "column": canonicalize(selected_col_display),           # normalize column
                        "new_value": final_value
                    }
                    try:
                        update_response = requests.post(
                            UPDATE_URL, json=payload,
                            headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
                        )
                        if update_response.status_code == 200:
                            st.success(update_response.json().get("message", "Updated."))
                            # Force-refetch to verify persistence
                            refreshed = fetch_data()
                            if refreshed.status_code == 200:
                                df = pd.DataFrame(refreshed.json())
                            else:
                                st.warning("Updated, but could not refresh data.")
                            st.rerun()
                        else:
                            # Show server message if any
                            try:
                                st.error(update_response.json().get("message", "Update failed."))
                            except:
                                st.error(f"Update failed with status {update_response.status_code}.")
                    except Exception as e:
                        st.error(f"Error updating via API: {e}")
    else:
        st.error("Failed to fetch data from API")
except Exception as e:
    st.error(f"Error connecting to API: {e}")
