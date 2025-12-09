
from flask import Flask, jsonify, request
import pandas as pd
from openpyxl import load_workbook
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from datetime import datetime
import time
import traceback
import re

app = Flask(__name__)

excel_file = 'Data.xlsx'
sheet_names = ['corp', 'EB', 'SS', 'PLD', 'AFFINITY', 'MINING']
final_df = None

TIMESTAMP_HEADER = "STATUS_UPDATED_AT"  # unified timestamp header

# ---------- Helpers ----------
def canonicalize(s: str) -> str:
    """Normalize names: strip punctuation/backticks/commas/colons/dashes; trim; uppercase."""
    if s is None:
        return ""
    s = str(s)
    s = re.sub(r"[`\.,:\-]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.upper()

def resolve_sheet(wb, sheet_input: str):
    """Match incoming sheet name (canonicalized) to an actual worksheet."""
    target = canonicalize(sheet_input)
    for name in wb.sheetnames:
        if canonicalize(name) == target:
            return wb[name]
    # Fallback using configured sheet_names aliases
    for name in sheet_names:
        if canonicalize(name) == target and name in wb.sheetnames:
            return wb[name]
    raise KeyError(f"Sheet '{sheet_input}' not found in workbook tabs: {wb.sheetnames}")

def header_index_maps(ws):
    """
    Build mappings for header row:
    - tuple_idx_map: canonical header -> 0-based index (for row[...] tuple access)
    - excel_idx_map: canonical header -> 1-based column index (for ws.cell(row, col))
    """
    header_cells = list(ws[1])
    tuple_idx_map = {}
    excel_idx_map = {}
    for i, cell in enumerate(header_cells):
        val = cell.value
        if val is None:
            continue
        ckey = canonicalize(val)
        tuple_idx_map.setdefault(ckey, i)
        excel_idx_map.setdefault(ckey, i + 1)
    return tuple_idx_map, excel_idx_map

# ---------- Load all sheets into one DataFrame ----------
def load_excel():
    global final_df
    try:
        combined_data = []
        for sheet in sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet, engine='openpyxl')
            df['SOURCE_SHEET'] = sheet
            combined_data.append(df)
        final_df = pd.concat(combined_data, ignore_index=True)
        print("Excel file reloaded!")
    except Exception as e:
        print("Error loading Excel:", e)
        final_df = pd.DataFrame([])

# Initial load
load_excel()

# ---------- Watchdog for auto-reload ----------
class ReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        # Depending on OS, event.src_path may be absolute path
        if event.src_path.endswith(excel_file):
            time.sleep(1)  # Avoid race condition with Excel writes
            load_excel()

def start_watcher():
    event_handler = ReloadHandler()
    observer = Observer()
    observer.schedule(event_handler, '.', recursive=False)
    observer.start()

# ---------- Routes ----------
@app.route('/', methods=['GET', 'HEAD'])
def home():
    return "✅ API is running! Use /data to get data or /update to update Excel."

@app.route('/health', methods=['GET', 'HEAD'])
def health():
    try:
        ready = final_df is not None and not final_df.empty
        return jsonify({"status": "ok", "ready": ready}), 200
    except Exception:
        return jsonify({"status": "ok", "ready": False}), 200

@app.route('/data', methods=['GET'])
def get_all_data():
    global final_df
    if final_df is None:
        load_excel()
    if final_df is None:
        return jsonify([])  # safe fallback
    return jsonify(final_df.to_dict(orient='records'))

# ---------- Update endpoint ----------
@app.route('/update', methods=['POST'])
def update_excel():
    try:
        data = request.json or {}
        sheet_in = data.get("sheet", "")
        client_code_in = data.get("client_code", "")
        column_in = data.get("column", "")
        new_value = data.get("new_value", "")

        if not sheet_in or not client_code_in or not column_in:
            return jsonify({"status": "error", "message": "Missing sheet, client_code, or column"}), 400

        # Normalize incoming keys (robust matching)
        canon_sheet = canonicalize(sheet_in)
        canon_column = canonicalize(column_in)
        # client code: strip spaces; compare case-insensitively later
        client_code_norm = str(client_code_in).strip()

        wb = load_workbook(excel_file)
        try:
            ws = resolve_sheet(wb, canon_sheet)
        except KeyError as e:
            return jsonify({"status": "error", "message": str(e)}), 400

        # Build header maps
        tuple_idx_map, excel_idx_map = header_index_maps(ws)

        # Resolve target status column by canonical name
        if canon_column not in tuple_idx_map:
            available = sorted(list(tuple_idx_map.keys()))
            return jsonify({
                "status": "error",
                "message": f"Column '{column_in}' not found. Available (canonical): {available}"
            }), 400

        status_tuple_idx = tuple_idx_map[canon_column]  # 0-based tuple index

        # Resolve (or create) timestamp column with a consistent 1-based index
        ts_canon = canonicalize(TIMESTAMP_HEADER)
        if ts_canon in excel_idx_map:
            ts_excel_col = excel_idx_map[ts_canon]
        else:
            ts_excel_col = ws.max_column + 1
            ws.cell(row=1, column=ts_excel_col, value=TIMESTAMP_HEADER)

        # Find row by CLIENT CODE (assumes first column is client code)
        updated = False
        for row in ws.iter_rows(min_row=2):
            cell_val = row[0].value
            if cell_val is None:
                continue
            if str(cell_val).strip().lower() == client_code_norm.lower():
                # Update status
                row[status_tuple_idx].value = new_value

                # Update timestamp
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                excel_row_num = row[0].row
                ws.cell(row=excel_row_num, column=ts_excel_col, value=current_time)

                # Save workbook with lock handling
                try:
                    wb.save(excel_file)
                except PermissionError:
                    return jsonify({"status": "error", "message": "Excel file is open. Please close it and try again."}), 500

                # Give FS a moment, then reload the in-memory dataframe
                time.sleep(1)
                load_excel()

                updated = True
                return jsonify({
                    "status": "success",
                    "message": f"Updated {column_in} for {client_code_in} to {new_value} at {current_time}"
                }), 200

        if not updated:
            return jsonify({"status": "error", "message": "Client Code not found"}), 404

    except Exception as e:
        print("Error:", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    threading.Thread(target=start_watcher, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
