import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

CSV_FILE = "leave_data.csv"

# -----------------------------
# LOAD & SAVE FUNCTIONS
# -----------------------------
def load_data():
    try:
        df = pd.read_csv(CSV_FILE)
        df["Leave From"] = pd.to_datetime(df["Leave From"])
        df["Leave End"] = pd.to_datetime(df["Leave End"])
        return df
    except:
        return pd.DataFrame(columns=["Name", "Leave From", "Leave End", "Duration"])

def save_data(df):
    df.to_csv(CSV_FILE, index=False)

# -----------------------------
# APP UI
# -----------------------------
st.set_page_config(page_title="IT Leave Planner 2025", layout="wide")

st.title("📅 IT Leave Planner - 2025")

df = load_data()

menu = st.sidebar.radio("Menu", ["Add Leave", "Leave Schedule", "Delete Leave Range"])

# -------------------------------------------------------
# 1️⃣ ADD LEAVE
# -------------------------------------------------------
if menu == "Add Leave":
    st.header("➕ Add New Leave")

    name = st.text_input("Employee Name")

    leave_from = st.date_input("Leave From")
    leave_end = st.date_input("Leave End")

    if st.button("Save Leave"):
        lf = pd.to_datetime(leave_from)
        le = pd.to_datetime(leave_end)

        if le < lf:
            st.error("Leave End cannot be before Leave From.")
        else:
            duration = (le - lf).days + 1
            new_row = pd.DataFrame([{
                "Name": name,
                "Leave From": lf,
                "Leave End": le,
                "Duration": f"{duration} days"
            }])

            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)

            st.success(f"Leave added successfully for {name}!")


# -------------------------------------------------------
# 2️⃣ LEAVE SCHEDULE
# -------------------------------------------------------
elif menu == "Leave Schedule":
    st.header("📘 Leave Schedule")

    if df.empty:
        st.info("No leave records found.")
    else:
        st.dataframe(df)


# -------------------------------------------------------
# 3️⃣ DELETE LEAVE RANGE
# -------------------------------------------------------
elif menu == "Delete Leave Range":
    st.header("🗑️ Delete Leave Range")

    if df.empty:
        st.warning("No leave records available to delete.")
    else:
        employees = df["Name"].unique()
        employee = st.selectbox("Select Employee", employees)

        start_date = st.date_input("Start of Range")
        end_date = st.date_input("End of Range")

        if start_date > end_date:
            st.error("Start date cannot be after End date.")
        else:
            if st.button("Delete Leave Entries"):
                sd = pd.to_datetime(start_date)
                ed = pd.to_datetime(end_date)

                # Find entries matching employee + overlapping date ranges
                mask = (df["Name"] == employee) & (
                    (df["Leave From"] <= ed) &
                    (df["Leave End"] >= sd)
                )

                deleted_rows = df[mask]

                if deleted_rows.empty:
                    st.warning("No matching leave entries found.")
                else:
                    df = df[~mask]
                    save_data(df)
                    st.success(f"Deleted {len(deleted_rows)} leave entries for {employee}.")
