
import streamlit as st
import requests
import pandas as pd
import re
import time
import io  # for in-memory Excel export

# -----------------------------
# PAGE CONFIG (enable wide layout for better responsiveness)
# -----------------------------
st.set_page_config(page_title="Office of the Customer Dashboard", layout="wide")

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
    - Exports exactly what is in the DataFrame (after filters & formatting).
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
# SIDEBAR CONTROLS (add compact mode & high contrast headers)
# -----------------------------
st.sidebar.header("FILTERS")

compact_mode = st.sidebar.toggle("Compact mode (better fit on phones/TVs)", value=True)
high_contrast = st.sidebar.toggle("High contrast headers", value=False)

# -----------------------------
# CUSTOM CSS (Light/Dark-safe + Responsive)
# -----------------------------
st.markdown(f"""
<style>
    /* Base container: reduce global paddings for small screens */
    .block-container {{
        padding-top: 2.0rem !important;
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        max-width: 100%;
    }}

    h1 {{
        margin-top: 0;
        text-align: center;
        line-height: 1.2;
    }}

    /* Scroll area for table */
    .scroll-container {{
        max-height: 60vh;        /* use viewport height for better fit */
        overflow-y: auto;
        overflow-x: auto;        /* allow horizontal scroll on narrow screens */
        border: 1px solid #ddd;
        padding: { '6px' if compact_mode else '10px' };
        border-radius: 8px;
        background: transparent;
    }}

    /* Ensure table uses full width and is responsive */
    .scroll-container table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: auto;      /* allow natural wrapping */
        font-size: { '0.88rem' if compact_mode else '0.95rem' };
    }}

    /* Header defaults (light mode) */
    .scroll-container table thead th {{
        position: sticky;
        top: 0;
        z-index: 2;
        background-color: #f8f9fa;          /* light gray */
        color: #1f2937;                      /* dark text */
        border-bottom: 1px solid #e5e7eb;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        font-weight: 700;
        white-space: normal;                 /* allow wrapping on narrow screens */
        padding: { '8px 10px' if compact_mode else '10px 12px' };
    }}

    /* Body cells */
    .scroll-container table tbody td {{
        color: inherit;
        padding: { '8px 10px' if compact_mode else '10px 12px' };
        vertical-align: top;
        word-wrap: break-word;
        white-space: normal;
    }}

    /* Improve row separation */
    .scroll-container table tbody tr td {{
        border-bottom: 1px solid #eee;
    }}

    /* Dark-mode via OS/browser preference */
    @media (prefers-color-scheme: dark) {{
        .scroll-container {{
            border-color: #374151;
        }}
        .scroll-container table thead th {{
            background-color: #1f2937;      /* dark slate */
            color: #f3f4f6;                 /* very light text */
            border-bottom: 1px solid #374151;
        }}
        /* Improve scrollbar contrast in dark mode */
        .scroll-container::-webkit-scrollbar {{
            width: 10px;
            height: 10px;
        }}
        .scroll-container::-webkit-scrollbar-thumb {{
            background-color: #4b5563;
            border-radius: 6px;
        }}
        .scroll-container::-webkit-scrollbar-track {{
            background-color: #1f2937;
        }}
    }}

    /* Dark-mode via Streamlit theme flag */
    .stApp[data-theme="dark"] .scroll-container table thead th {{
        background-color: #1f2937 !important;
        color: #f3f4f6 !important;
        border-bottom: 1px solid #374151 !important;
    }}

    /* Sticky first column for wide screens only (helps readability),
       but disable for very small screens to avoid overlap */
    @media (min-width: 600px) {{
        .scroll-container table tbody td:first-child,
        .scroll-container table thead th:first-child {{
            position: sticky;
            left: 0;
            background-clip: padding-box;
            background-color: inherit;
        }}
    }}

    /* Typography scaling by breakpoints for better fit */
    @media (max-width: 480px) {{
        h1 {{
            font-size: 1.1rem;
        }}
        .scroll-container {{
            max-height: 65vh;
        }}
        .scroll-container table {{
            font-size: { '0.82rem' if compact_mode else '0.9rem' };
        }}
        .scroll-container table thead th,
        .scroll-container table tbody td {{
            padding: { '6px 8px' if compact_mode else '8px 10px' };
        }}
    }}

    @media (min-width: 481px) and (max-width: 768px) {{
        h1 {{
            font-size: 1.3rem;
        }}
        .scroll-container table {{
            font-size: { '0.86rem' if compact_mode else '0.95rem' };
        }}
    }}
</style>
""", unsafe_allow_html=True)

# Optional high contrast override for headers
if high_contrast:
    st.markdown("""
    <style>
      .scroll-container table thead th {
          background-color: #0f172a !important;  /* even darker */
          color: #ffffff !important;              /* white text */
          border-bottom: 1px solid #1e293b !important;
      }
    </style>
    """, unsafe_allow_html=True)


# -----------------------------
# HEADER
# -----------------------------
col1, col2 = st.columns([2, 8])
with col1:
    st.image("minet.png", use_container_width=True)  # responsive image
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
# DISPLAY TABLE (HTML to retain styling)
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
        label="📥 Export displayed table to Excel",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Downloads the currently displayed table (after filters) as an Excel file."
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






