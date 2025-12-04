
#!/usr/bin/env python3
# leave_tracker.py
import json
import os
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

DATA_FILE = "leave_records.json"
HOLIDAYS_FILE = "public_holidays.json"
EXPORT_CSV = "leave_records_export.csv"

# -----------------------------
# File I/O
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
# Date helpers
# -----------------------------
def _next_id(records: List[Dict[str, Any]]) -> int:
    return (max(r["id"] for r in records) + 1) if records else 1

def _to_date(value: str) -> date:
    # Accepts YYYY-MM-DD (ISO)
    return date.fromisoformat(value)

def _iso(d: date) -> str:
    return d.isoformat()

def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return not (a_end < b_start or a_start > b_end)

# -----------------------------
# Duration calculators
# -----------------------------
def _calc_business_days(start: date, end: date) -> int:
    """
    Business days between start and end (inclusive), excluding weekends.
    """
    if end < start:
        return 0
    total_days = (end - start).days + 1
    weeks, remainder = divmod(total_days, 7)
    business_days = weeks * 5
    for i in range(remainder):
        d = start + timedelta(days=i)
        if d.weekday() < 5:  # Monday=0 ... Friday=4
            business_days += 1
    return business_days

def _calc_business_days_excl_holidays(start: date, end: date, holidays_dict: Dict[str, str]) -> int:
    """
    Business days minus holidays. Only subtracts holidays that fall on weekdays in the range.
    'holidays_dict' maps holiday name -> "YYYY-MM-DD".
    """
    if end < start:
        return 0

    # Base business days (Mon-Fri)
    business_days = _calc_business_days(start, end)

    # Normalize holiday dates
    holiday_dates = set()
    for _, iso in holidays_dict.items():
        try:
            holiday_dates.add(date.fromisoformat(iso))
        except ValueError:
            # Skip malformed date strings
            continue

    # Subtract only if the holiday falls on a weekday within range
    for h in holiday_dates:
        if start <= h <= end and h.weekday() < 5:
            business_days -= 1

    return max(business_days, 0)

# -----------------------------
# Core CRUD
# -----------------------------
def add_leave(name: str, leave_from: str, leave_end: str, duration: Optional[int] = None):
    records = _load_records()
    holidays = _load_holidays()

    start = _to_date(leave_from)
    end = _to_date(leave_end)
    if end < start:
        raise ValueError("leave_end cannot be before leave_from")

    # Duration: business days minus holidays (unless explicitly provided)
    if duration is None:
        dur = _calc_business_days_excl_holidays(start, end, holidays)
    else:
        dur = int(duration)

    # Overlap check for same person (by name, case-insensitive)
    for r in records:
        if r["name"].strip().lower() == name.strip().lower():
            if _overlaps(start, end, _to_date(r["leave_from"]), _to_date(r["leave_end"])):
                raise ValueError(
                    f"Overlap detected with record id {r['id']} "
                    f"({r['leave_from']} to {r['leave_end']}) for {name}."
                )

    new_rec = {
        "id": _next_id(records),
        "name": name.strip(),
        "leave_from": _iso(start),
        "leave_end": _iso(end),
        "duration": dur  # business days minus holidays
    }
    records.append(new_rec)
    # Keep records ordered by start date
    records.sort(key=lambda x: x["leave_from"])
    _save_records(records)
    return new_rec

def list_leaves(name: Optional[str] = None) -> List[Dict[str, Any]]:
    records = _load_records()
    if name:
        return [r for r in records if r["name"].strip().lower() == name.strip().lower()]
    return records

def update_leave(record_id: int, **fields):
    records = _load_records()
    holidays = _load_holidays()
    idx = next((i for i, r in enumerate(records) if r["id"] == record_id), None)
    if idx is None:
        raise ValueError(f"No record with id {record_id}")

    current = records[idx].copy()

    # Apply field changes
    if "name" in fields and fields["name"] is not None:
        current["name"] = str(fields["name"]).strip()

    if "leave_from" in fields and fields["leave_from"] is not None:
        current["leave_from"] = str(fields["leave_from"])
    if "leave_end" in fields and fields["leave_end"] is not None:
        current["leave_end"] = str(fields["leave_end"])

    # Recalculate duration if dates changed (or duration provided)
    start = _to_date(current["leave_from"])
    end = _to_date(current["leave_end"])
    if end < start:
        raise ValueError("leave_end cannot be before leave_from")

    if "duration" in fields and fields["duration"] is not None:
        current["duration"] = int(fields["duration"])
    else:
        current["duration"] = _calc_business_days_excl_holidays(start, end, holidays)

    # Overlap check within same person excluding this record
    for r in records:
        if r["id"] == record_id:
            continue
        if r["name"].strip().lower() == current["name"].strip().lower():
            if _overlaps(start, end, _to_date(r["leave_from"]), _to_date(r["leave_end"])):
                raise ValueError(
                    f"Overlap detected with record id {r['id']} "
                    f"({r['leave_from']} to {r['leave_end']}) for {current['name']}."
                )

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
        for r in records:
            writer.writerow(r)
    print(f"Exported {len(records)} rows to {path}")

def print_table(rows: List[Dict[str, Any]]):
    if not rows:
        print("(no records)")
        return
    widths = {
        "id": max(len("id"), max(len(str(r["id"])) for r in rows)),
        "name": max(len("name"), max(len(r["name"]) for r in rows)),
        "leave_from": len("leave_from"),
        "leave_end": len("leave_end"),
        "duration": len("duration")
    }
    header = f"{'id':>{widths['id']}}  {'name':<{widths['name']}}  {'leave_from':<10}  {'leave_end':<10}  {'duration':>8}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['id']:>{widths['id']}}  {r['name']:<{widths['name']}}  {r['leave_from']:<10}  {r['leave_end']:<10}  {r['duration']:>8}")

def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Local Leave Tracker (Business days minus holidays)")
    sub = parser.add_subparsers(dest="cmd")

    addp = sub.add_parser("add", help="Add a leave record")
    addp.add_argument("--name", required=True)
    addp.add_argument("--from", dest="leave_from", required=True, help="YYYY-MM-DD")
    addp.add_argument("--to", dest="leave_end", required=True, help="YYYY-MM-DD")
    addp.add_argument("--duration", type=int, help="Optional; overrides auto calculation")

    listp = sub.add_parser("list", help="List records")
    listp.add_argument("--name", help="Filter by name")

    upd = sub.add_parser("update", help="Update a record")
    upd.add_argument("--id", type=int, required=True)
    upd.add_argument("--name")
    upd.add_argument("--from", dest="leave_from")
    upd.add_argument("--to", dest="leave_end")
    upd.add_argument("--duration", type=int)

    dele = sub.add_parser("delete", help="Delete a record")
    dele.add_argument("--id", type=int, required=True)

    exp = sub.add_parser("export", help="Export to CSV")
    exp.add_argument("--out", default=EXPORT_CSV)

    args = parser.parse_args()
    try:
        if args.cmd == "add":
            rec = add_leave(args.name, args.leave_from, args.leave_end, args.duration)
            print("✅ Added:", rec)
        elif args.cmd == "list":
            rows = list_leaves(args.name)
            print_table(rows)
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
