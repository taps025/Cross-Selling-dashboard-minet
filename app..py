import streamlit as st
import calendar
from datetime import datetime, timedelta
import pandas as pd
import os

# ---------------------------------------------------------
# BOTSWANA PUBLIC HOLIDAYS
# ---------------------------------------------------------
BOTSWANA_HOLIDAYS = {
    "New Year's Day": "2025-01-01",
    "New Year Holiday": "2025-01-02",
    "Good Friday": "2025-04-02",
    "Easter Saturday": "2025-04-03",
    "Easter Monday": "2025-04-05",
    "Labour Day": "2025-05-01",
    "Ascension Day": "2025-05-13",
    "Sir Seretse Khama Day": "2025-07-01",
    "President's Day": "2025-07-19",
    "President's Day Holiday": "2025-07-20",
    "Botswana Day": "2025-09-30",
    "Botswana Day Holiday": "2025-10-01",
    "Christmas Day": "2025-12-25",
    "Boxing Day": "2025-12-26"
}

# Convert holiday strings → actual date objects
HOLIDAY_DATES = {datetime.strptime(d, "%Y-%m-%d").date() for d in BOTSWANA_HOLIDAYS.values()}

# ---------------------------------------------------------
# STREAMLIT SETUP
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="IT Leave Planner")

DATA_FILE = "leave_data.csv"

# ---------------------------------------------------------
# LOAD & SAVE DATA
# ---------------------------------------------------------
def load_leave_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)
        return df
    return pd.DataFrame(columns=["Employee", "Date"])

def save_leave_data(df):
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df.dropna(subset=["Date"], inplace=True)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    df.to_csv(DATA_FILE, index=False)

# ---------------------------------------------------------
# WORKING DAY CALCULATOR (EXCLUDES WEEKENDS & HOLIDAYS)
# ---------------------------------------------------------
def working_days_between(start_date, end_date):
    day_count = 0
    d = start_date
    while d <= end_date:
        if d.weekday() < 5 and d not in HOLIDAY_DATES:  # Monday–Friday & not a holiday
            day_count += 1
        d += timedelta(days=1)
    return day_count

# ---------------------------------------------------------
# GROUP CONSECUTIVE LEAVE DAYS
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
st.sidebar.header("Leave Planner")

current_year = datetime.now().year
year = st.sidebar.selectbox("Select Year", list(range(current_year - 5, current_year + 6)), index=5)

employees = ["Katlego Moleko", "Tapiwa Mlotshwa", "Christopher Kuteeue", "Siyabonga File", "Tsholofelo Tembwe"]
selected_employee = st.sidebar.selectbox("Select Employee", employees)

leave_dates = st.sidebar.date_input(
    "Select Leave Range", [],
    min_value=datetime(year, 1, 1),
    max_value=datetime(year, 12, 31)
)

if "leave_data" not in st.session_state:
    st.session_state.leave_data = load_leave_data()

st.session_state.leave_data["Date"] = pd.to_datetime(st.session_state.leave_data["Date"], errors="coerce")
st.session_state.leave_data.dropna(subset=["Date"], inplace=True)

# ---------------------------------------------------------
# ADD LEAVE
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# PAGE TITLE
# ---------------------------------------------------------
st.markdown(f"<h2 style='text-align:center;'>IT LEAVE PLANNER - {year}</h2>", unsafe_allow_html=True)

manager_view = st.sidebar.checkbox("Manager View")

# =========================================================
# MANAGER VIEW (WITH WORKING-DAY CALCULATOR)
# =========================================================
if manager_view:
    if st.session_state.leave_data.empty:
        st.info("No leave data available yet.")
    else:
        df = st.session_state.leave_data.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df.dropna(subset=["Date"], inplace=True)
        year_filtered = df[df["Date"].dt.year == year]

        if year_filtered.empty:
            st.warning(f"No leave data for {year}.")
        else:
            today = datetime.now().date()
            on_leave_today = year_filtered[year_filtered["Date"].dt.date == today]
            st.metric("People on Leave Today", len(on_leave_today))

            st.subheader("Leave Schedule")
            grouped_data = []

            for emp in year_filtered["Employee"].unique():
                emp_dates = sorted(year_filtered[year_filtered["Employee"] == emp]["Date"].tolist())
                start = emp_dates[0]
                end = emp_dates[0]

                for i in range(1, len(emp_dates)):
                    if emp_dates[i] == end + timedelta(days=1):
                        end = emp_dates[i]
                    else:
                        wd = working_days_between(start.date(), end.date())
                        grouped_data.append([emp, start.date(), end.date(), f"{wd} working days"])
                        start = emp_dates[i]
                        end = emp_dates[i]

                wd = working_days_between(start.date(), end.date())
                grouped_data.append([emp, start.date(), end.date(), f"{wd} working days"])

            leave_summary_df = pd.DataFrame(grouped_data, columns=["Name", "Leave From", "Leave End", "Duration"])
            st.table(leave_summary_df)

# =========================================================
# ENHANCED CALENDAR VIEW (unchanged)
# =========================================================
else:
    st.markdown("<h3>📅 Enhanced Leave Calendar</h3>", unsafe_allow_html=True)

    today = datetime.now().date()

    leave_dict = {}
    for _, row in st.session_state.leave_data.iterrows():
        leave_dict.setdefault(pd.to_datetime(row["Date"]).date(), []).append(row["Employee"])

    # Styling
    st.markdown("""
    <style>
    .calendar-container { display: flex; flex-wrap: wrap; gap: 20px; }
    .month-box { flex: 1 0 22%; padding: 10px; border-radius: 12px; border: 1px solid #ddd;
                 background: white; box-shadow: 2px 2px 8px rgba(0,0,0,0.08); }
    .day-cell { padding: 6px; text-align: center; border-radius: 8px; }
    .holiday { background-color: #d8f5dd; font-weight: bold; }
    .weekend { background-color: #f2f2f2; }
    .leave-day { background-color: #ffb3b3; font-weight: bold; }
    .today { border: 2px solid #1e90ff; }
    </style>
    """, unsafe_allow_html=True)

    html = "<div class='calendar-container'>"

    for month in range(1, 12 + 1):
        month_days = calendar.monthcalendar(year, month)
        html += "<div class='month-box'>"
        html += f"<h4 style='text-align:center;'>{calendar.month_name[month]}</h4>"
        html += "<table><tr>" + "".join([f"<th>{d}</th>" for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]) + "</tr>"

        for week in month_days:
            html += "<tr>"
            for i, day in enumerate(week):
                if day == 0:
                    html += "<td></td>"
                else:
                    date_obj = datetime(year, month, day).date()
                    classes = "day-cell"
                    tooltip = ""

                    if i >= 5:
                        classes += " weekend"

                    if date_obj in HOLIDAY_DATES:
                        classes += " holiday"
                        tooltip = "Public Holiday"

                    if date_obj in leave_dict:
                        classes += " leave-day"
                        tooltip += f" Leave: {', '.join(leave_dict[date_obj])}"

                    if date_obj == today:
                        classes += " today"

                    html += f"<td class='{classes}' title='{tooltip}'>{day}</td>"
            html += "</tr>"

        html += "</table></div>"

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

# ---------------------------------------------------------
# DELETE LEAVE RANGE
# ---------------------------------------------------------
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

            st.session_state.leave_data = st.session_state.leave_data[~(
                (st.session_state.leave_data["Employee"] == selected_employee_del) &
                (st.session_state.leave_data["Date"].dt.date >= start_date) &
                (st.session_state.leave_data["Date"].dt.date <= end_date)
            )]

            save_leave_data(st.session_state.leave_data)
            st.success(f"Deleted leave range {selected_range} for {selected_employee_del}.")
    else:
        st.info("No leave ranges found for this employee.")
