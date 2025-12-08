
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

app = Flask(__name__)

# ✅ Use persistent path from environment (Render Disk), fallback for local dev
excel_file = os.getenv("EXCEL_PATH", "Data.xlsx")

# Keep your sheet list exactly as is
sheet_names = ['corp', 'EB', 'SS', 'PLD', 'AFFINITY', 'MINING']
final_df = None

# ✅ Load all sheets into one DataFrame
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
        # Do not crash; keep final_df as-is so /data can respond gracefully
        print("Error loading Excel:", e)

# Initial load
load_excel()

# ✅ Watchdog handler for auto-reload (kept as in your original code)
class ReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        # Some environments emit full path, some base name; handle both
        if event.src_path.endswith(os.path.basename(excel_file)) or event.src_path.endswith(excel_file):
            time.sleep(1)  # Avoid race condition
            load_excel()

def start_watcher():
    event_handler = ReloadHandler()
    # Watch the directory containing the excel_file
    watch_dir = os.path.dirname(excel_file) or '.'
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=False)
    observer.start()

# ✅ Root route to avoid 404
@app.route('/')
def home():
    return "✅ API is running! Use /data to get data or /update to update Excel."

@app.route('/data', methods=['GET'])
def get_all_data():
    # Guard against None on startup failures
    if final_df is None:
        return jsonify({"status": "error", "message": "No data loaded"}), 503
    # Replace NaN with None for clean JSON
    safe_df = final_df.where(pd.notnull(final_df), None)
    return jsonify(safe_df.to_dict(orient='records'))

# ✅ Update endpoint with timestamp tracking and lock handling
@app.route('/update', methods=['POST'])
def update_excel():
    try:
        data = request.json or {}
        sheet = data.get("sheet")
        client_code = data.get("client_code")
        column = data.get("column")
        new_value = data.get("new_value")

        if not all([sheet, client_code, column]):
            return jsonify({"status": "error", "message": "Missing one of: sheet, client_code, column"}), 400

        wb = load_workbook(excel_file)
        if sheet not in wb.sheetnames:
            return jsonify({"status": "error", "message": f"Sheet '{sheet}' not found"}), 404
        ws = wb[sheet]

        # Find row by CLIENT CODE (assumes column A holds client code, as in your original)
        for row in ws.iter_rows(min_row=2):
            # Compare case-insensitively and safely
            cell_val = row[0].value
            if str(cell_val).lower() == str(client_code).lower():
                # Find column index for the target column (exact match, as in your original)
                col_idx = None
                for i, cell in enumerate(ws[1]):
                    if str(cell.value).strip() == column:
                        col_idx = i
                        break

                # Find column index for timestamp (case-insensitive)
                timestamp_col_idx = None
                for i, cell in enumerate(ws[1]):
                    if str(cell.value).strip().lower() == "status_updated_at":
                        timestamp_col_idx = i
                        break

                if col_idx is not None:
                    # Update status
                    row[col_idx].value = new_value

                    # Update timestamp
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if timestamp_col_idx is not None:
                        row[timestamp_col_idx].value = current_time
                    else:
                        # ✅ Fix: explicitly compute the new column index so we don't rely on ws.max_column changing mid-write
                        new_col = ws.max_column + 1  # openpyxl is 1-based for ws.cell
                        ws.cell(row=1, column=new_col, value="STATUS_UPDATED_AT")
                        # row[...] indexing is zero-based; convert new_col to zero-based index for row[]
                        row[new_col - 1].value = current_time

                    # ✅ Handle Excel lock and ensure persistence path is used
                    try:
                        wb.save(excel_file)
                    except PermissionError:
                        return jsonify({"status": "error", "message": "Excel file is open. Please close it and try again."}), 500

                    time.sleep(1)  # Avoid race condition with Watchdog
                    load_excel()
                    return jsonify({
                        "status": "success",
                        "message": f"Updated {column} for {client_code} to {new_value} at {current_time}"
                    })
                else:
                    return jsonify({"status": "error", "message": "Column not found"}), 400
        return jsonify({"status": "error", "message": "Client Code not found"}), 404
    except Exception as e:
        print("Error:", traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    threading.Thread(target=start_watcher, daemon=True).start()
    # Use $PORT in production (Render will set it). For local dev, 5000 is fine.
    port = int(os.getenv("PORT", "5000"))
