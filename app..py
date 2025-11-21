import streamlit as st
import calendar
from datetime import datetime, timedelta
import pandas as pd
import os

# ✅ Set wide layout
st.set_page_config(layout="wide")

# ✅ Botswana public holidays for 2025
botswana_holidays_2025 = [
    "2025-01-01", "2025-01-02", "2025-04-18", "2025-04-21", "2025-05-01", "2025-05-29",
    "2025-07-01", "2025-07-21", "2025-07-22", "2025-09-30", "2025-10-01", "2025-12-25", "2025-12-26"
]
botswana_holidays = set(pd.to_datetime(botswana_holidays_2025))

# ✅ File for persistence
DATA_FILE = "leave_data.csv"

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

# ✅ Calculate duration excluding weekends and holidays
def calculate_leave_duration(start_date, end_date):
    all_dates = pd.date_range(start=start_date, end=end_date)
    valid_dates = [d for d in all_dates if d.weekday() < 5 and d not in botswana_holidays]
    return len(valid_dates)

# ✅ Group consecutive dates into ranges
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

# Sidebar
st.sidebar.header("Leave Planner")
current_year = datetime.now().year
year = st.sidebar.selectbox("Select Year", list(range(current_year - 5, current_year + 6)), index=5)

employees = ["Katlego Moleko", "Tapiwa Mlotshwa", "Christopher Kuteeue", "Siyabonga File", "Tsholofelo Tembwe"]
selected_employee = st.sidebar.selectbox("Select Employee", employees)

leave_dates = st.sidebar.date_input("Select Leave Range", [], key="leave_range",
                                    min_value=datetime(year, 1, 1), max_value=datetime(year, 12, 31))

if "leave_data" not in st.session_state:
    st.session_state.leave_data = load_leave_data()

st.session_state.leave_data["Date"] = pd.to_datetime(st.session_state.leave_data["Date"], errors="coerce")
st.session_state.leave_data.dropna(subset=["Date"], inplace=True)

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

st.markdown(f"<h2 style='text-align:center;'>IT LEAVE PLANNER - {year}</h2>", unsafe_allow_html=True)

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
                        duration = calculate_leave_duration(start, end)
                        grouped_data.append([emp, start.date(), end.date(), f"{duration} working days"])
                        start = emp_dates[i]
                        end = emp_dates[i]
                duration = calculate_leave_duration(start, end)
                grouped_data.append([emp, start.date(), end.date(), f"{duration} working days"])

            leave_summary_df = pd.DataFrame(grouped_data, columns=["Name", "Leave From", "Leave End", "Duration"])
            st.table(leave_summary_df)
else:
    # ✅ Calendar styled for single-page view
    st.markdown("<h3 style='text-align:center;'>Leave Calendar</h3>", unsafe_allow_html=True)
    html = """
    <style>
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            width: 100%;
        }
        .month-box {
            border: 1px solid #ddd;
            border-radius: 2px;
            padding: 8px;
            background: #fff;
            font-size: 12px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: center;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 4px;
        }
        th {
            background: #f8f8f8;
            font-size: 11px;
        }
    </style>
    """
    html += '<div class="calendar-grid">'
    today = datetime.now().date()
    leave_dict = {}
    for _, row in st.session_state.leave_data.iterrows():
        leave_dict.setdefault(pd.to_datetime(row["Date"], errors="coerce").date(), []).append(row["Employee"])

    for month in range(1, 13):
        month_days = calendar.monthcalendar(year, month)
        html += f'<div class="month-box"><h4 style="text-align:center;margin-bottom:5px;">{calendar.month_name[month]}</h4>'
        html += "<table><tr>" + "".join([f"<th>{d}</th>" for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]]) + "</tr>"
        
        for week in month_days:
            html += "<tr>"
            for i, day in enumerate(week):
                if day == 0:
                    html += "<td></td>"
                else:
                    date_obj = datetime(year, month, day).date()
                    style = ""
                    if date_obj in leave_dict:
                        style += "font-weight:bold;"
                    if date_obj == today:
                        style += "border:2px solid #2ecc71;"
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

