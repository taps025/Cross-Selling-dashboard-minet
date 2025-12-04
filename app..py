

#!/usr/bin/env python3
import json
import os
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

DATA_FILE = "leave_records.json"
HOLIDAYS_FILE = "public_holidays.json"
EXPORT_CSV = "leave_records_export.csv"

# -----------------------------
# File Handling
# -----------------------------
def _ensure_file(path: str, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f, indent=2)

def _load_records() -> List[Dict[str, Any]]:
    _ensure_file(DATA_FILE, [])
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def _save_records(records: List[Dict[str, Any]]):
    with open(DATA_FILE, "w") as f:
        json.dump(records, f, indent=2)

def _load_holidays() -> Dict[str, str]:
    _ensure_file(HOLIDAYS_FILE, {})
    with open(HOLIDAYS_FILE, "r") as f:
        return json.load(f)

# -----------------------------
# Helpers
# -----------------------------
def _next_id(records: List[Dict[str, Any]]) -> int:
    return (max(r["id"] for r in records) + 1) if records else 1

def _to_date(value: str) -> date:
    return date.fromisoformat(value)

def _iso(d: date) -> str:
    return d.isoformat()

def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return not (a_end < b_start or a_start > b_end)

# -----------------------------
# Duration Calculation
# -----------------------------
def _calc_business_days_excl_holidays(start: date, end: date, holidays_dict: Dict[str, str]) -> int:
    if end < start:
        return 0

    # Base business days (Mon-Fri)
    business_days = 0
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            business_days += 1
        d += timedelta(days=1)

    # Subtract holidays that fall on weekdays
    holiday_dates = {date.fromisoformat(v) for v in holidays_dict.values()}
    for h in holiday_dates:
        if start <= h <= end and h.weekday() < 5:
            business_days -= 1

    return max(business_days, 0)

# -----------------------------
# CRUD Operations
# -----------------------------
def add_leave(name: str, leave_from: str, leave_end: str, duration: Optional[int] = None):
    records = _load_records()
    holidays = _load_holidays()

    start = _to_date(leave_from)
    end = _to_date(leave_end)
    if end < start:
        raise ValueError("leave_end cannot be before leave_from")

    dur = duration if duration else _calc_business_days_excl_holidays(start, end, holidays)

    # Overlap check
    for r in records:
        if r["name"].lower() == name.lower():
            if _overlaps(start, end, _to_date(r["leave_from"]), _to_date(r["leave_end"])):
                raise ValueError(f"Overlap detected with record id {r['id']} ({r['leave_from']} to {r['leave_end']})")

    new_rec = {
        "id": _next_id(records),
        "name": name.strip(),
        "leave_from": _iso(start),
        "leave_end": _iso(end),
        "duration": dur
    }
    records.append(new_rec)
    records.sort(key=lambda x: x["leave_from"])
    _save_records(records)
    return new_rec

def list_leaves(name: Optional[str] = None) -> List[Dict[str, Any]]:
    records = _load_records()
    return [r for r in records if not name or r["name"].lower() == name.lower()]

def update_leave(record_id: int, **fields):
    records = _load_records()
    holidays = _load_holidays()
    idx = next((i for i, r in enumerate(records) if r["id"] == record_id), None)
    if idx is None:
        raise ValueError(f"No record with id {record_id}")

    current = records[idx]
    if fields.get("name"): current["name"] = fields["name"]
    if fields.get("leave_from"): current["leave_from"] = fields["leave_from"]
    if fields.get("leave_end"): current["leave_end"] = fields["leave_end"]

    start = _to_date(current["leave_from"])
    end = _to_date(current["leave_end"])
    if end < start:
        raise ValueError("leave_end cannot be before leave_from")

    current["duration"] = fields.get("duration") or _calc_business_days_excl_holidays(start, end, holidays)

    records[idx] = current
    records.sort(key=lambda x: x["leave_from"])
    _save_records(records)
    return current

def delete_leave(record_id: int):
    records = _load_records()
    new_records = [r for r in records if r["id"] != record_id]
    if len(new_records) == len(records):
        raise ValueError(f"No record with id {record_id}")
    _save_records(new_records)
    return True

# -----------------------------
# Export & CLI
# -----------------------------
def export_csv(path: str = EXPORT_CSV):
    import csv
    records = _load_records()
    if not records:
        print("No data to export.")
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "leave_from", "leave_end", "duration"])
        writer.writeheader()
        writer.writerows(records)
    print(f"Exported {len(records)} rows to {path}")

def print_table(rows: List[Dict[str, Any]]):
    if not rows:
        print("(no records)")
        return
    print("\n=== LEAVE TRACKER (Business Days Minus Holidays) ===\n")
    print(f"{'ID':<4} {'Name':<20} {'From':<12} {'To':<12} {'Duration':<8}")
    print("-" * 60)
    for r in rows:
        print(f"{r['id']:<4} {r['name']:<20} {r['leave_from']:<12} {r['leave_end']:<12} {r['duration']:<8}")

def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Leave Tracker CLI")
    sub = parser.add_subparsers(dest="cmd")

    addp = sub.add_parser("add")
    addp.add_argument("--name", required=True)
    addp.add_argument("--from", dest="leave_from", required=True)
    addp.add_argument("--to", dest="leave_end", required=True)
    addp.add_argument("--duration", type=int)

    listp = sub.add_parser("list")
    listp.add_argument("--name")

    upd = sub.add_parser("update")
    upd.add_argument("--id", type=int, required=True)
    upd.add_argument("--name")
    upd.add_argument("--from", dest="leave_from")
    upd.add_argument("--to", dest="leave_end")
    upd.add_argument("--duration", type=int)

    dele = sub.add_parser("delete")
    dele.add_argument("--id", type=int, required=True)

    exp = sub.add_parser("export")
    exp.add_argument("--out", default=EXPORT_CSV)

    args = parser.parse_args()
    try:
        if args.cmd == "add":
            rec = add_leave(args.name, args.leave_from, args.leave_end, args.duration)
            print("✅ Added:", rec)
        elif args.cmd == "list":
            print_table(list_leaves(args.name))
        elif args.cmd == "update":
            updates = {k: v for k, v in {
                "name": args.name,
                "leave_from": args.leave_from,
                "leave_end": args.leave_end,
                "duration": args.duration
            }.items() if v is not None}
            rec = update_leave(args.id, **updates)
            print("✅ Updated:", rec)
        elif args.cmd == "delete":
            delete_leave(args.id)
            print(f"✅ Deleted id {args.id}")
        elif args.cmd == "export":
            export_csv(args.out)
        else:
            parser.print_help()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    cli()

