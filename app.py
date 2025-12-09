import streamlit as st
import requests
import pandas as pd
import re
import time

# -----------------------------
# CONFIG
# -----------------------------
API_URL = "https://api-minet.onrender.com/data"
UPDATE_URL = "https://api-minet.onrender.com/update"

# -----------------------------
# Canonicalize Helper (UI-safe)
# -----------------------------
def canonicalize(name: str) -> str:
    if not isinstance(name, str):
        return ""
    base = re.sub(r"[`\.,:\-]+", "", name)
    base = re.sub(r"\s+", " ", base).strip()
    return base.upper()


# -----------------------------
# PAGE CSS
# -----------------------------
st.markdown("""
    <style>
        .block-container {
            padding-top: 2.9rem !important;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        h1 { text-align: center; margin-top: 0; color:#2C3E50; }
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

# -----------------------------
# HEADER
# -----------------------------
col1, col2 = st.columns([2, 8])
with col1:
    st.image("minet.png", width=180)
with col2:
    st.markdown("<h1>OFFICE OF THE CUSTOMER DASHBOARD</h1>", unsafe_allow_html=True)


# -----------------------------
# FETCH API DATA
# -----------------------------
try:
    response = requests.get(
        API_URL,
        params={"_ts": int(time.time())},  # cache-buster
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
        timeout=20
    )

    if response.status_code == 200:
        df = pd.DataFrame(response.json())

        # -----------------------------
        # SIDEBAR FILTERS
        # -----------------------------
        st.sidebar.header("FILTERS")
        sheet_filter = st.sidebar.selectbox("DEPARTMENT", df["SOURCE_SHEET"].unique().tolist())
        client_filter = st.sidebar.text_input("CLIENT NAME")

        st.sidebar.subheader("CHANGE STATUS")
        client_code_input = st.sidebar.text_input("Enter Client Code to Edit")

        # FILTER BY SHEET
        filtered_df = df[df["SOURCE_SHEET"] == sheet_filter].copy()

        if client_filter:
            filtered_df = filtered_df[
                filtered_df["CLIENT NAME"].str.contains(client_filter, case=False, na=False)
            ]

        # -----------------------------
        # SELECT COLUMNS BASED ON SHEET
        # -----------------------------
        sheet_columns = {
            "SS": ["CLIENT CODE", "CLIENT NAME", "PREMIUM,", "CORPORATE.", "PERSONAL LINES.", "AFFINITY.", "EMPLOYEE BENEFITS."],
            "corp": ["CLIENT CODE", "CLIENT NAME", "PREMIUM.", "EMPLOYEE BENEFITS", "PERSONAL LINES", "STAFF SCHEMES"],
            "EB": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE-", "AFFINITY-", "STAFF SCHEMES-", "PERSONAL LINES-"],
            "PLD": ["CLIENT CODE", "CLIENT NAME", "PREMIUM;", "CORPORATE:", "STAFF SCHEMES:", "EMPLOYEE BENEFITS:", "AFFINITY:", "MINING:"],
            "AFFINITY": ["CLIENT CODE", "CLIENT NAME", "PREMIUM:", "EMPLOYEE BENEFITS,", "STAFF SCHEMES,", "PERSONAL LINES,"],
            "MINING": ["CLIENT CODE", "CLIENT NAME", "PREMIUM`", "EMPLOYEE BENEFITS`", "AFFINITY`", "STAFF SCHEMES`", "PERSONAL LINES`"],
        }

        columns_to_show = sheet_columns.get(sheet_filter, filtered_df.columns.tolist())
        available_cols = [c for c in columns_to_show if c in filtered_df.columns]

        display_df = filtered_df[available_cols]

        # FILTER BY CLIENT CODE
        if client_code_input:
            display_df = display_df[
                display_df["CLIENT CODE"].astype(str).str.strip().str.lower() ==
                client_code_input.strip().lower()
            ]

        # -----------------------------
        # PREMIUM FORMATTING
        # -----------------------------
        for col in display_df.columns:
            if "PREMIUM" in col.upper():
                display_df[col] = display_df[col].apply(
                    lambda x: f"{float(x):,.2f}" if pd.notnull(x) and str(x).replace('.', '', 1).isdigit()
                    else str(x)
                )

        # -----------------------------
        # CROSS-SELL HIGHLIGHT
        # -----------------------------
        def highlight_cross_sell(val):
            return "color: red; font-weight: bold;" if str(val).strip().lower() == "cross-sell" else ""

        styled_df = display_df.style.applymap(highlight_cross_sell).hide(axis="index")
        st.markdown(f'<div class="scroll-container">{styled_df.to_html()}</div>', unsafe_allow_html=True)

        # -----------------------------
        # EDIT SECTION
        # -----------------------------
        if client_code_input:
            st.markdown("### Edit Client Details")

            if display_df.empty:
                st.warning("No client found with that code.")
            else:
                editable_cols = [c for c in display_df.columns if c not in ["CLIENT CODE", "CLIENT NAME"]]

                selected_col = st.selectbox("Select Column to Edit", editable_cols)
                new_value_option = st.selectbox("Select New Value", ["Cross-Sell", "Shared Client"])

                if st.button("Apply Change"):
                    payload = {
                        "sheet": canonicalize(sheet_filter),
                        "client_code": client_code_input.strip(),
                        "column": canonicalize(selected_col),
                        "new_value": new_value_option
                    }

                    try:
                        update_res = requests.post(UPDATE_URL, json=payload, timeout=20)

                        if update_res.status_code == 200:
                            st.success(update_res.json().get("message", "Updated successfully."))

                            # force fresh fetch
                            requests.get(API_URL, params={"_ts": int(time.time())})

                            st.rerun()
                        else:
                            st.error(update_res.json().get("message", f"Update failed ({update_res.status_code})"))
                    except Exception as err:
                        st.error(f"Error updating data: {err}")

    else:
        st.error("Failed to fetch data from API")

except Exception as e:
    st.error(f"Error connecting to API: {e}")
