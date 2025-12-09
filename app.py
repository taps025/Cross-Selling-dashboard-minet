
import streamlit as st
import requests
import pandas as pd
import re
import time
import io  # for in-memory Excel export

# -----------------------------
# PAGE CONFIG (wide layout improves responsiveness)
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
# CUSTOM CSS (Auto-responsive + Dark-mode safe + Logo-safe header)
# -----------------------------
st.markdown("""
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
