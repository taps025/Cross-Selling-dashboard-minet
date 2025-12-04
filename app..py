import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# -----------------------------
# PERMANENT FILE STORAGE
# -----------------------------
CSV_FILE = os.path.join(os.path.expanduser("~"), "leave_data.csv")

# Create file if missing
if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=["Name", "Leave From", "Leave End", "Duration"]).to_csv(CSV_FILE, index=False)


# -----------------------------
# HOLIDAYS (MONTH, DAY ONLY)
# -----------------------------
HOLIDAYS_MD = [
    (1, 1), (1, 2),
    (4, 2),
    (5, 1), (5, 5), (5, 13),
    (7, 1), (7, 19), (7, 20),
    (9, 30),
    (10, 1),
    (12, 25), (12, 26)
]

# -----------------------------
# LOAD & SAVE FUNCTIONS
# -----------------------------
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_FILE)
    df["Leave From"] = pd.to_datetime(df["Leave From"], errors="coerce")
    df["Leave End"] = pd.to_datetime(df["Leave End"], errors="coerce")
    return df


def save_data(df):
    df.to_csv(CSV_FILE, index=False)
    load_data.clear()  # refresh cache


# -----------------------------
# CALCULATE WORKING DAYS
# -----------------------------
def calculate_leave_duration(start, end):
    total_days = pd.date_range(start, end)
    valid_days = []

    for day in total_days:
        weekday = day.weekday() < 5
        holiday = (day.month, day.day) in HOLIDAYS_MD
        if weekday and not holiday:
            valid_days.append(day)

    return len(valid_days)


# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title="Leave Planner", layout="wide")
st.title("📅 IT LEAVE PLANNER")

df = load_data()
menu = st.sidebar.radio("MENU", ["ADD LEAVE", "LEAVE SCHEDULE", "DELETE LEAVE RANGE"])


# -------------------------------------------------------
# 1️⃣ ADD LEAVE
# -------------------------------------------------------
if menu == "ADD LEAVE":
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
                "Duration": f"{duration} days"
            }])

            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)
            st.success(f"Leave added for {name} ({duration} working days)")


# -------------------------------------------------------
# 2️⃣ LEAVE SCHEDULE
# -------------------------------------------------------
elif menu == "LEAVE SCHEDULE":
    st.header("📘 Leave Schedule")
    df = load_data()

    if df.empty:
        st.info("No leave data available.")
    else:
        st.dataframe(df)


# -------------------------------------------------------
# 3️⃣ DELETE LEAVE RANGE
# -------------------------------------------------------
elif menu == "DELETE LEAVE RANGE":
    st.header("🗑️ Delete Leave Range")

    df = load_data()

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


