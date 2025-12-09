from flask import Flask, jsonify, request
if str(cell_val).strip().lower() == client_code_norm.lower():
# Update status (use tuple index)
row[col_tuple_idx].value = new_value


# Update timestamp
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
excel_row_num = row[0].row
ws.cell(row=excel_row_num, column=ts_excel_col, value=current_time)


# Save workbook with retries to handle transient file locks
save_err = None
for attempt in range(3):
try:
wb.save(excel_file)
save_err = None
break
except PermissionError as pe:
save_err = pe
time.sleep(0.8)


if save_err:
return jsonify({"status": "error", "message": "Excel file is open. Please close it and try again."}), 500


# Give FS a moment, then reload the in-memory dataframe
time.sleep(0.6)
load_excel()


updated = True
return jsonify({
"status": "success",
"message": f"Updated {column_in} for {client_code_in} to {new_value} at {current_time}",
"attempted_match": attempted_keys
}), 200


if not updated:
return jsonify({"status": "error", "message": "Client Code not found"}), 404


except Exception as e:
print("Error:", traceback.format_exc())
return jsonify({"status": "error", "message": str(e)}), 500




if __name__ == '__main__':
threading.Thread(target=start_watcher, daemon=True).start()
app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
