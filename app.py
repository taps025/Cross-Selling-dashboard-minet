
import streamlit as st
import requests
import pandas as pd
import re
import time
import io
import os
import base64

# -----------------------------
# PAGE CONFIG
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
    """Convert a DataFrame to an Excel file in-memory and return bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.book[sheet_name]
        for column_cells in ws.iter_cols(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
            max_len = 0
            for cell in column_cells:
                val_len = len(str(cell.value)) if cell.value is not None else 0
                if val_len > max_len:
                    max_len = val_len
            ws.column_dimensions[column_cells[0].column_letter].width = max_len + 2
    output.seek(0)
    return output.getvalue()

def embed_image_base64(image_path: str) -> str:
    """Return a data URI for an image, or empty string if not found."""
    if not os.path.exists(image_path):
        return ""
    with open(image_path, "rb") as f:
        data = f.read()
    # Infer mime type
    lower = image_path.lower()
    if lower.endswith(".png"):
        mime = "image/png"
    elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
        mime = "image/jpeg"
    elif lower.endswith(".svg"):
        # Streamlit won't inline raw SVG here; prefer PNG/JPG.
        # If you do use SVG, convert to PNG or serve via st.image.
        mime = "image/svg+xml"
    else:
        mime = "image/png"
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"

# -----------------------------
# CSS & HEADER HTML
# -----------------------------
CSS = '''
<style>
    /* Base container: mobile-first paddings */
    .block-container {
        padding-top: 2.0rem !important;
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        max-width: 100%;
    }

    /* Header row with safe logo area */
    .header-row {
        display: grid;
        grid-template-columns: auto 1fr;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;
    }
    .logo-wrap {
        padding: 6px 8px;               /* safe area to prevent clipping */
        overflow: visible !important;    /* don't clip the img */
    }
    .logo-wrap img {
        display: block;
        max-height: 64px;                /* adjust to desired visual size */
        width: auto;                     /* keep aspect ratio */
        height: auto;
        object-fit: contain;             /* avoid cropping */
    }
    .app-title {
        margin: 0;
        line-height: 1.15;
        font-weight: 800;
        font-size: 1.75rem;              /* desktop default */
        color: #1f2937;
        text-align: left;
    }
    @media (prefers-color-scheme: dark) {
        .app-title { color: #f3f4f6; }
    }
    .stApp[data-theme="dark"] .app-title { color: #f3f4f6 !important; }

    /* Scroll area for table */
    .scroll-container {
        max-height: 60vh;                /* use viewport height to fit screens */
        overflow-y: auto;
        overflow-x: auto;                /* horizontal scroll for narrow devices */
        border: 1px solid #ddd;
        padding: 8px;
        border-radius: 8px;
        background: transparent;
    }

    /* Table fits width and wraps content */
    .scroll-container table {
        width: 100%;
        border-collapse: collapse;
        table-layout: auto;              /* allow natural wrapping */
        font-size: 0.92rem;
    }

    /* Header (light mode default) */
    .scroll-container table thead th {
        position: sticky;
        top: 0;
        z-index: 2;
        background-color: #f8f9fa;
        color: #1f2937;
        border-bottom: 1px solid #e5e7eb;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        font-weight: 700;
        white-space: normal;             /* allow wrapping */
        padding: 10px 12px;
    }

    /* Body cells */
    .scroll-container table tbody td {
        color: inherit;
        padding: 10px 12px;
        vertical-align: top;
        word-wrap: break-word;
        white-space: normal;
        border-bottom: 1px solid #eee;
    }

    /* Dark-mode via OS/browser preference */
    @media (prefers-color-scheme: dark) {
        .scroll-container {
            border-color: #374151;
        }
        .scroll-container table thead th {
            background-color: #1f2937;
            color: #f3f4f6;
            border-bottom: 1px solid #374151;
        }
        /* Better scrollbar contrast in dark mode */
        .scroll-container::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        .scroll-container::-webkit-scrollbar-thumb {
            background-color: #4b5563;
            border-radius: 6px;
        }
        .scroll-container::-webkit-scrollbar-track {
            background-color: #1f2937;
        }
    }

    /* Dark-mode via Streamlit theme flag */
    .stApp[data-theme="dark"] .scroll-container table thead th {
        background-color: #1f2937 !important;
        color: #f3f4f6 !important;
        border-bottom: 1px solid #374151 !important;
    }

    /* Sticky first column for wider screens only */
    @media (min-width: 600px) {
        .scroll-container table tbody td:first-child,
        .scroll-container table thead th:first-child {
            position: sticky;
            left: 0;
            background-clip: padding-box;
            background-color: inherit;
        }
    }

    /* Typography scaling for phones */
    @media (max-width: 480px) {
        .logo-wrap img { max-height: 48px; }
        .app-title { font-size: 1.25rem; }
        .scroll-container { max-height: 65vh; }
        .scroll-container table { font-size: 0.86rem; }
        .scroll-container table thead th,
        .scroll-container table tbody td { padding: 8px 10px; }
    }

    /* Small tablets */
    @media (min-width: 481px) and (max-width: 768px) {
        .app-title { font-size: 1.45rem; }
        .scroll-container table { font-size: 0.9rem; }
    }
</style>
'''

# Use Base64-embedded logo (bullet-proof across hosting)
logo_path = "minet.png"   # <-- ensure this exists next to app.py (or change to assets/minet.png)
logo_data_uri = embed_image_base64(logo_path)

HEADER_HTML = f'''
<div class="header-row">
  <div class="logo-wrap">
    {'<img src="' + logo_data_uri + '" alt="Minet logo">' if logo_data_uri else ''}
  </div>
  <h1 class="app-title">OFFICE OF THE CUSTOMER DASHBOARD</h1>
</div>
'''

# Inject CSS and header
st.markdown(CSS, unsafe_allow_html=True)
if logo_data_uri:
    st.markdown(HEADER_HTML, unsafe_allow_html=True)
else:
    # Fallback showing a warning and attempt to render via st.image
    st.warning("Logo file not found. Please ensure 'minet.png' is in the app directory.")
    col_logo, col_title = st.columns([2, 8])
    with col_logo:
        try:
            st.image(logo_path, use_container_width=True)
        except Exception:
            pass
    with col_title:
        st.markdown('<h1 class="app-title">OFFICE OF THE CUSTOMER DASHBOARD</h1>', unsafe_allow_html=True)

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
st.markdown('<div class="scroll-container">' + styled_df.to_html() + '</div>', unsafe_allow_html=True)

# -----------------------------
# EXPORT TO EXCEL (Displayed table)
# -----------------------------
if not display_df.empty:
    excel_bytes = df_to_excel_bytes(display_df, sheet_name=sheet_filter or "Data")
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"office_of_customer_{sheet_filter}_{ts}.xlsx"
    st.download_button(
        label="📥 Export  to Excel",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Download table as an Excel file."
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
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(update_response.json().get("message", "Update failed."))
            except Exception as e:
                st.error(f"Error updating API: {e}")
