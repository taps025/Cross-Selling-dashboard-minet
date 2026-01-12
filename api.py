
# api.py
from flask import Flask, jsonify, request
import pandas as pd
from openpyxl import load_workbook
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from datetime import datetime
import time
import traceback
import os
import re
import sqlite3
import logging

# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------
EXCEL_FILE = os.environ.get("EXCEL_FILE", "Data.xlsx")
SHEETS = [s.strip() for s in os.environ.get("SHEETS", "corp,EB,SS,PLD,AFFINITY,MINING").split(",") if s.strip()]
OVERRIDES_DB = os.environ.get("OVERRIDES_DB", "overrides.db")

# Allowed values for the status column (enforce if you want strict control)
ALLOWED_STATUS_VALUES = {"CROSS-SELL", "SHARED CLIENT"}

# Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# In-memory cache of combined data (Excel -> pandas)
final_df = pd.DataFrame()

# ------------------------------------------------------------------------------
# Helpers: canonicalization & header/row lookup
# ------------------------------------------------------------------------------
def canon(s: str) -> str:
    """Canonicalize header names to avoid punctuation/case mismatches."""
    if s is None:
        return ""
    s = re.sub(r"[`.,:\-\[\]]+", "", str(s))  # strip punctuation variants
    s = re.sub(r"\s+", " ", s).strip()
    return s.upper()

def find_header_index(ws, target_header: str):
    """Return the ZERO-based index of the header that matches target_header (canonical)."""
    target_c = canon(target_header)
    for i, cell in enumerate(ws[1]):  # header row is 1
        if canon(cell.value) == target_c:
            return i
    return None

def worksheet_headers(ws):
    """Return list of header strings from the first row."""
    return [cell.value for cell in ws[1]]

def get_row_dict(ws, row_idx_1based: int) -> dict:
    """Read a row into a dict of header->value."""
    headers = worksheet_headers(ws)
    values = [cell.value for cell in ws[row_idx_1based]]
    return {str(h): v for h, v in zip(headers, values)}

# ------------------------------------------------------------------------------
# SQLite overrides (persisting user-edited values)
# ------------------------------------------------------------------------------
def db():
    conn = sqlite3.connect(OVERRIDES_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS overrides(
            sheet TEXT NOT NULL,
            client_code TEXT NOT NULL,
            column_canon TEXT NOT NULL,
            column_actual TEXT NOT NULL,
            new_value TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY (sheet, client_code, column_canon)
        )
    """)
    conn.commit()
    conn.close()

def apply_overrides(rows: list[dict]) -> list[dict]:
    """
    Merge base rows with overrides so user changes persist even if Excel is refreshed.
    Overrides are keyed by (sheet, client_code, column_actual).
    """
    if not rows:
        return rows
    conn = db()
    ovs = conn.execute("SELECT sheet, client_code, column_actual, new_value FROM overrides").fetchall()
    conn.close()
    idx = {(r["sheet"], r["client_code"], r["column_actual"]): r["new_value"] for r in ovs}
    out = []
    for r in rows:
        sheet = str(r.get("SOURCE_SHEET", ""))
        code  = str(r.get("CLIENT CODE", ""))
        nr = dict(r)
        # apply any overrides for this row
        for k in list(nr.keys()):
            key = (sheet, code, k)
            if key in idx:
                nr[k] = idx[key]
        out.append(nr)
    return out

# ------------------------------------------------------------------------------
# Excel load / reload (watchdog on file changes)
# ------------------------------------------------------------------------------
def load_excel():
    global final_df
    try:
        combined_data = []
        for sheet in SHEETS:
            df = pd.read_excel(EXCEL_FILE, sheet_name=sheet, engine="openpyxl")
            df["SOURCE_SHEET"] = sheet
            combined_data.append(df)
        final_df = pd.concat(combined_data, ignore_index=True) if combined_data else pd.DataFrame()
        app.logger.info("✅ Excel file reloaded.")
    except Exception as e:
        app.logger.error(f"❌ Error loading Excel: {e}")
        final_df = pd.DataFrame()

class ReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        # Simple filename match; in some setups event.src_path is absolute
        if os.path.basename(event.src_path) == os.path.basename(EXCEL_FILE):
            time.sleep(0.5)  # small delay to avoid partial writes
            load_excel()

def start_watcher():
    event_handler = ReloadHandler()
    observer = Observer()
    # watch the directory containing the Excel file
    watch_dir = os.path.dirname(os.path.abspath(EXCEL_FILE)) or "."
    observer.schedule(event_handler, watch_dir, recursive=False)
    observer.start()

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return "✅ API is running! Use /data to get data or POST /update to update Excel."

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "rows_cached": int(final_df.shape[0])})

@app.route("/data", methods=["GET"])
def get_all_data():
    base = final_df.to_dict(orient="records") if not final_df.empty else []
    merged = apply_overrides(base)
    return jsonify(merged)

@app.route("/update", methods=["POST"])
def update_excel():
    """
    Request JSON:
    {
      "sheet": "corp",
      "client_code": "C001",
      "column": "Status",       # visible header from the UI
      "new_value": "Shared Client"
    }
    """
    try:
        data = request.json or {}
        sheet = data.get("sheet")
        client_code = (data.get("client_code") or "").strip()
        column_visible = data.get("column")
        new_value = data.get("new_value")

        if not all([sheet, client_code, column_visible]):
            return jsonify({"status": "error", "message": "Missing sheet, client_code, or column"}), 400

        # If updating STATUS, optionally enforce allowed values
        if canon(column_visible) == "STATUS":
            if canon(new_value) not in ALLOWED_STATUS_VALUES:
                return jsonify({
                    "status": "error",
                    "message": "Invalid status. Use 'Cross-Sell' or 'Shared Client'."
                }), 400

        # Open workbook / validate sheet
        wb = load_workbook(EXCEL_FILE)
        if sheet not in wb.sheetnames:
            return jsonify({"status": "error", "message": f"Sheet '{sheet}' not found"}), 404
        ws = wb[sheet]

        # Find header indices by canonical names
        client_code_col_idx = find_header_index(ws, "CLIENT CODE")
        if client_code_col_idx is None:
            return jsonify({"status": "error", "message": "CLIENT CODE header not found"}), 400

        target_col_idx = find_header_index(ws, column_visible)
        if target_col_idx is None:
            return jsonify({"status": "error", "message": f"Column '{column_visible}' not found"}), 400

        # Find row (case-insensitive match on CLIENT CODE)
        target_row_idx = None  # 1-based index for openpyxl
        for row in ws.iter_rows(min_row=2):  # skip header row
            cell_val = row[client_code_col_idx].value
            if cell_val is not None and str(cell_val).strip().lower() == client_code.lower():
                target_row_idx = row[0].row
                break
        if target_row_idx is None:
            return jsonify({"status": "error", "message": f"Client Code '{client_code}' not found"}), 404

        # Update the cell (openpyxl column indices are 1-based)
        ws.cell(row=target_row_idx, column=target_col_idx + 1, value=new_value)

        # Ensure STATUS_UPDATED_AT column exists; set timestamp
        ts_header_idx = find_header_index(ws, "STATUS_UPDATED_AT")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if ts_header_idx is None:
            # Create new timestamp column at the end
            new_ts_col_1based = ws.max_column + 1
            ws.cell(row=1, column=new_ts_col_1based, value="STATUS_UPDATED_AT")
            ws.cell(row=target_row_idx, column=new_ts_col_1based, value=current_time)
        else:
            ws.cell(row=target_row_idx, column=ts_header_idx + 1, value=current_time)

        # Save workbook (handle Excel lock)
        try:
            wb.save(EXCEL_FILE)
        except PermissionError:
            return jsonify({"status": "error", "message": "Excel file is open. Please close it and try again."}), 500

        # ALSO persist into overrides (bulletproof against ETL/refresh)
        headers = worksheet_headers(ws)
        actual_header = headers[target_col_idx] if target_col_idx < len(headers) else column_visible
        now_epoch = int(time.time())

        conn = db()
        conn.execute("""
            INSERT INTO overrides(sheet, client_code, column_canon, column_actual, new_value, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sheet, client_code, column_canon)
            DO UPDATE SET new_value=excluded.new_value,
                          updated_at=excluded.updated_at,
                          column_actual=excluded.column_actual
        """, (sheet, client_code, canon(column_visible), actual_header, str(new_value), now_epoch))
        conn.commit()
        conn.close()

        # Small delay then reload combined DF
        time.sleep(0.5)
        load_excel()

        # Confirm by reading back the Excel row
        live_row = get_row_dict(ws, target_row_idx)
        return jsonify({
            "status": "success",
            "message": f"Updated {actual_header} for {client_code} to '{new_value}' at {current_time}",
            "sheet": sheet,
            "client_code": client_code,
            "column_actual": actual_header,
            "new_value": live_row.get(actual_header, new_value),
            "updated_at": current_time
        })

    except Exception as e:
        app.logger.error("Error:\n" + traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------------------------------------------------------------------
# Boot
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # Initialize DB and load Excel once
    init_db()
    load_excel()
    # Start watchdog in background
    threading.Thread(target=start_watcher, daemon=True).start()
    # Run API
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)



