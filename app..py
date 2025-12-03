import streamlit as st
import pandas as pd
from datetime import datetime

CSV_FILE = "leave_data.csv"

# -----------------------------
# HOLIDAYS (full list provided)
# -----------------------------
HOLIDAYS = [
    "2025-01-01",  # New Year's Day
    "2025-01-02",  # New Year Holiday
    "2025-04-02",  # Good Friday
    "2025-05-05",  # Easter Monday
    "2025-05-01",  # Labour Day
    "2025-05-13",  # Ascension Day
    "2025-07-01",  # Sir Seretse Khama Day
    "2025-07-19",  # Presidents Day
    "2025-07-20",  # Presidents Day Holiday
    "2025-09-30",  # Botswana Day
    "2025-10-01",  # Botswana Day Holiday
    "2025-12-25",  # Christmas
    "2025-12-26",  # Boxing Day
]

HOLIDAYS = pd.to_datetime(HOLIDAYS)

# -----------------------------
# LOAD & SAVE FUNCTIONS
# -----------------------------
def load_data():
    try:
        df = pd.read_csv(CSV_FILE)
        df["Leave From"] = pd.to_datetime(df["Leave From"], errors="coerce")
        df["Leave End"] = pd.to_datetime(df["Leave End"], errors="coerce")
        return df
    except:
        return pd.DataFrame(columns=["Name", "Leave From", "Leave End", "Duration"])

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# -----------------------------
# CALCULATE DURATION EXCLUDING WEEKENDS & HOLIDAYS
# -----------------------------
def calculate_leave_duration(start, end):
    # Generate all business days between start and end
    business_days = pd.bdate_range(start, end)
    # Remove holidays
    valid_days = [d for d in business_days if d not in HOLIDAYS]
    return len(valid_days)

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title="Leave Planner", layout="wide")
st.title("📅 IT LEAVE PLANNER")

df = load_data()
menu = st.sidebar.radio("Menu", ["Add Leave", "Leave Schedule", "Delete Leave Range"])

# -------------------------------------------------------
# 1️⃣ ADD LEAVE
# -------------------------------------------------------
if menu == "Add Leave":
    st.header("➕ Add Leave")

    name = st.text_input("Employee Name")
    leave_from = st.date_input("Leave From")
    leave_end = st.date_input("Leave End")

    if st.button("Save Leave"):
        lf = pd.to_datetime(leave_from)
        le = pd.to_datetime(leave_end)

        if le < lf:
            st.error("End date cannot be before start date.")
        else:
            duration = calculate_leave_duration(lf, le)
            new_row = pd.DataFrame([{
                "Name": name,
                "Leave From": lf,
                "Leave End": le,
                "Duration": f"{duration} working days"
            }])

            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)
            st.success(f"Leave added for {name} ({duration} working days)")

# -------------------------------------------------------
# 2️⃣ LEAVE SCHEDULE
# -------------------------------------------------------
elif menu == "Leave Schedule":
    st.header("📘 Leave Schedule")
    if df.empty:
        st.info("No leave data available.")
    else:
        st.dataframe(df)

# -------------------------------------------------------
# 3️⃣ DELETE LEAVE RANGE
# -------------------------------------------------------
elif menu == "Delete Leave Range":
    st.header("🗑️ Delete Leave Range")

    if df.empty:
        st.warning("No data to delete.")
    else:
        employees = df["Name"].unique()
        employee = st.selectbox("Select Employee", employees)

        start_date = st.date_input("Start of Range")
        end_date = st.date_input("End of Range")

        if start_date > end_date:
            st.error("Start date cannot be after end date.")
        else:
            if st.button("Delete Leave Entries"):
                sd = pd.to_datetime(start_date)
                ed = pd.to_datetime(end_date)

                mask = (
                    (df["Name"] == employee)
                    & (df["Leave From"] <= ed)
                    & (df["Leave End"] >= sd)
                )

                deleted = df[mask]

                if deleted.empty:
                    st.warning("No matching leave entries found.")
                else:
                    df = df[~mask]
                    save_data(df)
                    st.success(f"Deleted {len(deleted)} leave entries for {employee}.")
