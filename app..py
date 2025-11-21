import streamlit as st
import calendar
from datetime import datetime, timedelta
import pandas as pd
import os

# ✅ Set wide layout
st.set_page_config(layout="wide")

# ✅ File for persistence
DATA_FILE = "leave_data.csv"

# ✅ Load data from CSV if exists
def load_leave_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df.dropna(subset=["Date"], inplace=True)
        return df
    return pd.DataFrame(columns=["Employee", "Date"])

# ✅ Save data to CSV
def save_leave_data(df):
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df.dropna(subset=["Date"], inplace=True)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    df.to_csv(DATA_FILE, index=False)

# ✅ FIXED: Group consecutive dates into ranges
def get_leave_ranges(df, employee):
    emp_dates = sorted(pd.to_datetime(df[df["Employee"] == employee]["Date"], errors="coerce").dropna().tolist())
    ranges = []
    if emp_dates:
        start = emp_dates[0]
        end = emp_dates[0]
        for i in range(1, len(emp_dates)):
            if emp_dates[i] == end + timedelta(days=1):
                end = emp_dates[i]
            else:
                ranges.append((start.date(), end.date()))
                start = emp_dates[i]
                end = emp_dates[i]
        ranges.append((start.date(), end.date()))
    return ranges

# Sidebar for filters
st.sidebar.header("Leave Planner")
current_year = datetime.now().year
year = st.sidebar.selectbox("Select Year", list(range(current_year - 5, current_year + 6)), index=5)

# Employee selection
employees = ["Katlego Moleko", "Tapiwa Mlotshwa", "Christopher Kuteeue", "Siyabonga File", "Tsholofelo Tembwe"]
selected_employee = st.sidebar.selectbox("Select Employee", employees)

# ✅ Date range selection
leave_dates = st.sidebar.date_input("Select Leave Range", [], key="leave_range",
                                    min_value=datetime(year, 1, 1), max_value=datetime(year, 12, 31))

# ✅ Initialize session state
if "leave_data" not in st.session_state:
    st.session_state.leave_data = load_leave_data()

# ✅ Ensure Date column is datetime globally
st.session_state.leave_data["Date"] = pd.to_datetime(st.session_state.leave_data["Date"], errors="coerce")
st.session_state.leave_data.dropna(subset=["Date"], inplace=True)

# ✅ Add Leave and Save
if st.sidebar.button("Add Leave"):
    if len(leave_dates) == 2:
        start_date, end_date = leave_dates
        all_dates = pd.date_range(start=start_date, end=end_date).tolist()
        for date in all_dates:
            if not ((st.session_state.leave_data["Employee"] == selected_employee) &
                    (st.session_state.leave_data["Date"] == pd.to_datetime(date))).any():
                st.session_state.leave_data = pd.concat([
                    st.session_state.leave_data,
                    pd.DataFrame({"Employee": [selected_employee], "Date": [pd.to_datetime(date)]})
                ], ignore_index=True)
        save_leave_data(st.session_state.leave_data)

# ✅ Centered Titles
st.markdown(f"<h2 style='text-align:center;'>IT LEAVE PLANNER - {year}</h2>", unsafe_allow_html=True)

# Manager View toggle
manager_view = st.sidebar.checkbox("Manager View")

if manager_view:
    if st.session_state.leave_data.empty:
        st.info("No leave data available yet.")
    else:
        df = st.session_state.leave_data.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)
        year_filtered_data = df[df["Date"].dt.year == year]

        if year_filtered_data.empty:
            st.warning(f"No leave data for {year}.")
        else:
            today = datetime.now().date()
            on_leave_today = year_filtered_data[year_filtered_data["Date"].dt.date == today]
            st.metric("People on Leave Today", len(on_leave_today))

            st.subheader("Leave Schedule")
            grouped_data = []
            for emp in year_filtered_data["Employee"].unique():
                emp_dates = sorted(year_filtered_data[year_filtered_data["Employee"] == emp]["Date"].tolist())
                start = emp_dates[0]
                end = emp_dates[0]
                for i in range(1, len(emp_dates)):
                    if emp_dates[i] == end + timedelta(days=1):
                        end = emp_dates[i]
                    else:
                        duration = len(pd.date_range(start=start, end=end))
                        grouped_data.append([emp, start.date(), end.date(), f"{duration} days"])
                        start = emp_dates[i]
                        end = emp_dates[i]
                duration = len(pd.date_range(start=start, end=end))
                grouped_data.append([emp, start.date(), end.date(), f"{duration} days"])

            leave_summary_df = pd.DataFrame(grouped_data, columns=["Name", "Leave From", "Leave End", "Duration"])
            st.table(leave_summary_df)
else:
    st.markdown("<h3>Leave Calendar</h3>", unsafe_allow_html=True)
    html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px;">'
    today = datetime.now().date()
    leave_dict = {}
    for _, row in st.session_state.leave_data.iterrows():
        leave_dict.setdefault(pd.to_datetime(row["Date"], errors="coerce").date(), []).append(row["Employee"])

    for month in range(1, 13):
        month_days = calendar.monthcalendar(year, month)
        html += f'<div><h4 style="text-align:center;">{calendar.month_name[month]}</h4>'
        html += "<table style='width:100%;border-collapse:collapse;'><tr>" + "".join([f"<th>{d}</th>" for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]) + "</tr>"
        for week in month_days:
            html += "<tr>"
            for i, day in enumerate(week):
                if day == 0:
                    html += "<td></td>"
                else:
                    date_obj = datetime(year, month, day).date()
                    style = ""
                    if date_obj in leave_dict:
                        style = "font-weight:bold;"  # Leave days bold
                    if date_obj == today:
                        style += " border:2px solid #2ecc71;"
                    html += f"<td style='{style}'>{day}</td>"
            html += "</tr>"
        html += "</table></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

# ✅ Delete Leave Range
st.markdown("<h4>Delete Leave Range</h4>", unsafe_allow_html=True)
if not st.session_state.leave_data.empty:
    employees = st.session_state.leave_data["Employee"].unique().tolist()
    selected_employee_del = st.selectbox("Select Employee", employees)
    leave_ranges = get_leave_ranges(st.session_state.leave_data, selected_employee_del)
    range_options = [f"{r[0]} to {r[1]}" for r in leave_ranges]
    if range_options:
        selected_range = st.selectbox("Select Leave Range to Delete", range_options)
        if st.button("Delete Range"):
            start_str, end_str = selected_range.split(" to ")
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            before_count = len(st.session_state.leave_data)
            st.session_state.leave_data = st.session_state.leave_data[~(
                (st.session_state.leave_data["Employee"] == selected_employee_del) &
                (st.session_state.leave_data["Date"].dt.date >= start_date) &
                (st.session_state.leave_data["Date"].dt.date <= end_date)
            )]
            after_count = len(st.session_state.leave_data)
            save_leave_data(st.session_state.leave_data)
            st.success(f"Deleted leave range {selected_range} for {selected_employee_del}. Rows removed: {before_count - after_count}")
    else:
        st.info("No leave ranges found for this employee.")
