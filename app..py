import pandas as pd
from supabase import create_client, Client

# -----------------------------
# SUPABASE CONFIGURATION
# -----------------------------
SUPABASE_URL = "https://wxxhmbxsdtxobtjbckhl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind4eGhtYnhzZHR4b2J0amJja2hsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ3OTE3ODAsImV4cCI6MjA4MDM2Nzc4MH0.lKFr4VEGY71M00yo6x1hbCr_iX2MIiG_2Qrnh2Yr_rk"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# READ OLD CSV
# -----------------------------
CSV_FILE = "leave_data.csv"  # Path to your old CSV

df = pd.read_csv(CSV_FILE)

# Make sure columns are correct
df = df.rename(columns={
    "Name": "name",
    "Leave From": "leave_from",
    "Leave End": "leave_end",
    "Duration": "duration"
})

# Convert dates to proper format
df["leave_from"] = pd.to_datetime(df["leave_from"]).dt.date
df["leave_end"] = pd.to_datetime(df["leave_end"]).dt.date

# Convert duration to integer if it has " days" text
df["duration"] = df["duration"].astype(str).str.replace(" days", "").astype(int)

# -----------------------------
# INSERT INTO SUPABASE
# -----------------------------
for _, row in df.iterrows():
    supabase.table("leave_records").insert({
        "name": row["name"],
        "leave_from": row["leave_from"],
        "leave_end": row["leave_end"],
        "duration": row["duration"]
    }).execute()

print(f"✅ Migrated {len(df)} leave records to Supabase successfully!")


