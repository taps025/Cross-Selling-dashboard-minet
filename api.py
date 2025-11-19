from flask import Flask, jsonify, request
import pandas as pd
from openpyxl import load_workbook
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
from datetime import datetime
import time
import traceback

app = Flask(__name__)

excel_file = 'Data.xlsx'
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
        print("Error loading Excel:", e)

# Initial load
load_excel()

# ✅ Watchdog handler for auto-reload
class ReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(excel_file):
            time.sleep(1)  # Avoid race condition
            load_excel()

def start_watcher():
    event_handler = ReloadHandler()
    observer = Observer()
    observer.schedule(event_handler, '.', recursive=False)
    observer.start()

# ✅ Root route to avoid 404
@app.route('/')
def home():
    return "✅ API is running! Use /data to get data or /update to update Excel."

@app.route('/data', methods=['GET'])
def get_all_data():
    return jsonify(final_df.to_dict(orient='records'))

# ✅ Update endpoint with timestamp tracking and lock handling
@app.route('/update', methods=['POST'])
def update_excel():
    try:
        data = request.json
        sheet = data.get("sheet")
        client_code = data.get("client_code")
        column = data.get("column")
        new_value = data.get("new_value")

        wb = load_workbook(excel_file)
        ws = wb[sheet]

        # Find row by CLIENT CODE
        for row in ws.iter_rows(min_row=2):
            if str(row[0].value).lower() == client_code.lower():
                # Find column index for the target column
                col_idx = None
                for i, cell in enumerate(ws[1]):
                    if str(cell.value).strip() == column:
                        col_idx = i
                        break

                # Find column index for timestamp
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
                        ws.cell(row=1, column=ws.max_column + 1, value="STATUS_UPDATED_AT")
                        ws.cell(row=row[0].row, column=ws.max_column, value=current_time)

                    # ✅ Handle Excel lock
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
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
    
