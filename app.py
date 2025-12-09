
import streamlit as st
import requests
import pandas as pd
import re
import time
import io  # NEW: for in-memory Excel export

# -----------------------------
# CONFIG
# -----------------------------
API_URL = "https://api-minet.onrender.com/data"
UPDATE_URL = "https://api-minet.onrender.com/update"


# -----------------------------
# HELPERS
# -----------------------------
def canonicalize(name: str) -> str:
    """Normalize names for matching in Excel/API."""
    if not isinstance(name, str):
        return ""
    base = re.sub(r"[`\.,:\-]+", "", name)
    base = re.sub(r"\s+", " ", base).strip()
    return base.upper()


def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    """
    Convert a DataFrame to an Excel file in-memory and return bytes.
    - Exports exactly what is in the DataFrame (e.g., after filters & formatting).
    - Applies a simple column auto-fit for readability.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

        # Auto-fit column widths based on content length
        ws = writer.book[sheet_name]
        for column_cells in ws.iter_cols(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
            max_len = 0
            for cell in column_cells:
                try:
                    val_len = len(str(cell.value)) if cell.value is not None else 0
                except Exception:
                    val_len = 0
                if val_len > max_len:
                    max_len = val_len
            ws.column_dimensions[column_cells[0].column_letter].width = max_len + 2

    output.seek(0)
    return output.getvalue()


# -----------------------------
# CUSTOM CSS
# -----------------------------
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
# LOAD DATA FROM API
# -----------------------------
try:
    response = requests.get(
        API_URL,
        params={'_ts': int(time.time())},
        headers={'Cache-Control': 'no-cache'},
        timeout=20
    )

    if response.status_code == 200:
        df = pd.DataFrame(response.json())
    else:
        st.error("Failed to fetch data from API.")
        st.stop()

except Exception as e:
    st.error(f"Error connecting to API: {e}")
    st.stop()


# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("FILTERS")

sheet_filter = st.sidebar.selectbox("DEPARTMENT", options=df["SOURCE_SHEET"].unique().tolist())
client_filter = st.sidebar.text_input("CLIENT NAME")

client_code_input = st.sidebar.text_input("Enter Client Code to Edit")


# -----------------------------
# FILTER DATA
# -----------------------------
filtered_df = df[df["SOURCE_SHEET"] == sheet_filter].copy()

if client_filter:
    filtered_df = filtered_df[
        filtered_df["CLIENT NAME"].str.contains(client_filter, case=False, na=False)
    ]


# -----------------------------
# SELECT COLUMNS BASED ON SHEET
# -----------------------------
column_map = {
    "SS": ["CLIENT CODE", "CLIENT NAME", "PREMIUM,", "CORPORATE.", "PERSONAL LINES.", "AFFINITY.", "EMPLOYEE BENEFITS."],
    "corp": ["CLIENT CODE", "CLIENT NAME", "PREMIUM.", "EMPLOYEE BENEFITS", "PERSONAL LINES", "STAFF SCHEMES"],
    "EB": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE-", "AFFINITY-", "STAFF SCHEMES-", "PERSONAL LINES-"],
    "PLD": ["CLIENT CODE", "CLIENT NAME", "PREMIUM;", "CORPORATE:", "STAFF SCHEMES:", "EMPLOYEE BENEFITS:", "AFFINITY:", "MINING:"],
    "AFFINITY": ["CLIENT CODE", "CLIENT NAME", "PREMIUM:", "EMPLOYEE BENEFITS,", "STAFF SCHEMES,", "PERSONAL LINES,"],
    "MINING": ["CLIENT CODE", "CLIENT NAME", "PREMIUM`", "EMPLOYEE BENEFITS`", "AFFINITY`", "STAFF SCHEMES`", "PERSONAL LINES`"]
}

columns_to_show = column_map.get(sheet_filter, filtered_df.columns.tolist())
available_cols = [c for c in columns_to_show if c in filtered_df.columns]
display_df = filtered_df[available_cols].copy()


# -----------------------------
# FILTER BY CLIENT CODE
# -----------------------------
if client_code_input:
    display_df = display_df[
        display_df["CLIENT CODE"].astype(str).str.strip().str.lower() ==
        client_code_input.strip().lower()
    ].copy()


# -----------------------------
# FORMAT PREMIUM COLUMNS
# -----------------------------
# Keep your formatted strings for display/export
for col in display_df.columns:
    if "PREMIUM" in col.upper():
        display_df.loc[:, col] = display_df[col].apply(
            lambda x: (
                f"{float(x):,.2f}"
                if pd.notnull(x) and str(x).replace('.', '', 1).isdigit()
                else x
            )
        )


# -----------------------------
# COLOR HIGHLIGHT FUNCTION
# -----------------------------
def highlight_cross_sell(val):
    return "color: red; font-weight: bold;" if str(val).strip().lower() == "cross-sell" else ""


# -----------------------------
# DISPLAY TABLE
# -----------------------------
styled_df = display_df.style.applymap(highlight_cross_sell).hide(axis="index")
st.markdown(f'<div class="scroll-container">{styled_df.to_html()}</div>', unsafe_allow_html=True)


# -----------------------------
# EXPORT TO EXCEL (of the displayed table)
# -----------------------------
if not display_df.empty:
    excel_bytes = df_to_excel_bytes(display_df, sheet_name=sheet_filter or "Data")
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"office_of_customer_{sheet_filter}_{ts}.xlsx"

    st.download_button(
        label="📥 Export to Excel",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Download  displayed table as an Excel file."
    )
else:
    st.info("No rows to export for the current filters.")


# -----------------------------
# EDIT SECTION
# -----------------------------
if client_code_input:
    if display_df.empty:
        st.warning("No client found with that code.")
    else:
        st.markdown("### Edit Client Details")

        editable_cols = [c for c in display_df.columns if c not in ["CLIENT CODE", "CLIENT NAME"]]

        selected_col = st.selectbox("Select Column to Edit", options=editable_cols)
        new_value = st.selectbox("Select New Value", ["Cross-Sell", "Shared Client"])

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

                    # Force refresh after update
                    time.sleep(1)
                    st.rerun()

                else:
                    st.error(update_response.json().get("message", "Update failed."))

            except Exception as e:
                st.error(f"Error updating API: {e}")


