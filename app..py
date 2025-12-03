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
        df["Leave From"] = pd.to_datetime(df["Leave From"], errors="coerce")
        df["Leave End"] = pd.to_datetime(df["Leave End"], errors="coerce")
        return df
    except:
        return pd.DataFrame(columns=["Name", "Leave From", "Leave End", "Duration"])

def save_data(df):
    df.to_csv(CSV_FILE, index=False)


# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title="Leave Planner", layout="wide")

st.title("IT LEAVE PLANNER")

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
            duration = (le - lf).days + 1
            new_row = pd.DataFrame([{
                "Name": name,
                "Leave From": lf,
                "Leave End": le,
                "Duration": f"{duration} days"
            }])

            df = pd.concat([df, new_row], ignore_index=True)
            save_data(df)

            st.success(f"Leave added for {name}")


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
# 3️⃣ DELETE LEAVE RANGE (FIXED VERSION)
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

                # FIXED: ensure comparison uses datetime only
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

