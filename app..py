import streamlit as st
import calendar
from datetime import datetime, timedelta
import pandas as pd
import os

# ✅ Set wide layout and remove default padding
st.set_page_config(layout="wide")
st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-left: 0rem;
    padding-right: 0rem;
    max-width: 100%;
}
.center-title {
    text-align: center;
    font-size: 48px;
    font-weight: bold;
    margin-bottom: 10px;
    margin-top: 40px;
}
.center-subtitle {
    text-align: center;
    font-size: 20px;
    font-weight: bold;
    margin-bottom: 20px;
}
.calendar-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr); /* ✅ 4 months per row */
    gap: 10px;
    width: 100%;
}
.month-box {
    background-color: #f8f9fa;
    border-radius: 6px;
    padding: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    text-align: center;
    font-family: Arial, sans-serif;
    font-size: 12px;
}
.month-title {
    font-size: 14px;
    font-weight: bold;
    color: #2c3e50;
    margin-bottom: 6px;
}
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
}
th, td {
    padding: 2px;
    text-align: center;
    border: 1px solid #ccc;
}
th {
    background-color: #eaeaea;
}
.weekend {
    background-color: #f0f0f0;
}
.today {
    border: 2px solid #2ecc71;
}
.leave-day {
    background-color: #ffcccc;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

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

# ✅ Group consecutive dates into ranges
def get_leave_ranges(df, employee):
    emp_dates = sorted(df[df["Employee"] == employee]["Date"].tolist())
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
leave_dates = st.sidebar.date_input("Select Leave Range", [], key="leave_range", min_value=datetime(year, 1, 1), max_value=datetime(year, 12, 31))

# ✅ Initialize session state
if "leave_data" not in st.session_state:
    st.session_state.leave_data = load_leave_data()

# ✅ Ensure Date column is datetime globally before any .dt usage
st.session_state.leave_data["Date"] = pd.to_datetime(st.session_state.leave_data["Date"], errors="coerce")
st.session_state.leave_data.dropna(subset=["Date"], inplace=True)

# ✅ Add Leave and Save
if st.sidebar.button("Add Leave"):
    if len(leave_dates) == 2:
        start_date, end_date = leave_dates
        all_dates = pd.date_range(start=start_date, end=end_date).tolist()

        for date in all_dates:
            if not ((st.session_state.leave_data["Employee"] == selected_employee) & (st.session_state.leave_data["Date"] == pd.to_datetime(date))).any():
                st.session_state.leave_data = pd.concat([st.session_state.leave_data, pd.DataFrame({"Employee": [selected_employee], "Date": [pd.to_datetime(date)]})], ignore_index=True)

        save_leave_data(st.session_state.leave_data)

# ✅ Centered Titles
st.markdown(f"<div class='center-title'>IT LEAVE PLANNER - {year}</div>", unsafe_allow_html=True)

# Manager View toggle
manager_view = st.sidebar.checkbox("Manager View")

if manager_view:
    # ✅ Show analytics only
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
    # ✅ Show Calendar
    st.markdown("<div class='center-subtitle'>Leave Calendar</div>", unsafe_allow_html=True)

    html = '<div class="calendar-grid">'
    today = datetime.now().date()

    leave_dict = {}
    for _, row in st.session_state.leave_data.iterrows():
        leave_dict.setdefault(pd.to_datetime(row["Date"], errors="coerce").date(), []).append(row["Employee"])

    for month in range(1, 13):
        month_days = calendar.monthcalendar(year, month)
        html += f'<div class="month-box"><div class="month-title">{calendar.month_name[month]}</div>'
        html += "<table><tr>" + "".join([f"<th>{d}</th>" for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]) + "</tr>"
        for week in month_days:
            html += "<tr>"
            for i, day in enumerate(week):
                if day == 0:
                    html += "<td></td>"
                else:
                    date_obj = datetime(year, month, day).date()
                    style = ""
                    tooltip = ""
                    if date_obj in leave_dict:
                        style = "background-color:#ffcccc; font-weight:bold;"
                        tooltip = ", ".join(leave_dict[date_obj])
                    if i >= 5:
                        style += " background-color:#f0f0f0;"
                    if date_obj == today:
                        style += " border:2px solid #2ecc71;"
                    html += f"<td style='{style}' title='{tooltip}'>{day}</td>"
            html += "</tr>"
        html += "</table></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # ✅ Delete Leave Range only in Calendar view
    st.markdown("<hr><h3>Delete Leave Range</h3>", unsafe_allow_html=True)
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