import streamlit as st
import pandas as pd

# ✅ Page Config
st.set_page_config(page_title="Cross-Selling Tracker", layout="wide")

# ✅ Display logo and title
col1, col2 = st.columns([2, 8])
with col1:
    st.image("minet.png", width=350)
with col2:
    st.markdown("<h3 style='margin:0; color:#2C3E50; white-space:nowrap;'>OFFICE OF THE CUSTOMER CROSS-SELLING ACTIVITY TRACKER</h3>", unsafe_allow_html=True)

# ✅ Custom CSS
st.markdown("""
    <style>
        .block-container {
            padding-top: 2.9rem !important;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        img {
            margin-top: 10px;
        }
        table {
            width: 100% !important;
            border-collapse: collapse;
        }
        thead th {
            position: sticky;
            top: 0;
            background-color: #f8f9fa;
            z-index: 2;
        }
    </style>
""", unsafe_allow_html=True)

# ✅ Load Data Function
def load_data():
    excel_file = 'Data.xlsx'
    sheet_names = ['corp', 'EB', 'SS', 'PLD', 'AFFINITY', 'MINING']

    combined_data = []
    for sheet in sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet, engine='openpyxl')
        df['SOURCE_SHEET'] = sheet
        combined_data.append(df)

    final_df = pd.concat(combined_data, ignore_index=True)
    return final_df
# table function 

# ✅ Display Table Function
def display_table(df):
    df['STATUS_UPDATED_AT'] = pd.to_datetime(df['STATUS_UPDATED_AT'], errors='coerce')
    df['Month'] = df['STATUS_UPDATED_AT'].dt.month_name()

    pivot_df = df.dropna(subset=['STATUS_UPDATED_AT']).pivot_table(
        index='ACCOUNT HOLDER', columns='Month', values='STATUS_UPDATED_AT', aggfunc='count'
    )

    all_months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
    pivot_df = pivot_df.reindex(columns=all_months, fill_value=0)

    all_holders = df['ACCOUNT HOLDER'].dropna().unique()
    pivot_df = pivot_df.reindex(all_holders, fill_value=0)

    def font_color(val):
        if isinstance(val, (int, float)):
            return 'color: green; font-weight: bold;' if val >= 5 else 'color: red; font-weight: bold;'
        return ''

    styled_df = pivot_df.style.applymap(font_color, subset=all_months)
    st.write(styled_df.to_html(), unsafe_allow_html=True)

# ✅ Reset Table Function
def reset_table(df):
    all_months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
    all_holders = df['ACCOUNT HOLDER'].dropna().unique()

    # Create zeroed-out DataFrame
    zero_df = pd.DataFrame(0, index=all_holders, columns=all_months)

    styled_df = zero_df.style.applymap(lambda x: 'color: red; font-weight: bold;')
    st.write(styled_df.to_html(), unsafe_allow_html=True)

# ✅ Main Logic
final_df = load_data()

# ✅ Reset Button Only
if st.button("⛔ Reset Table to Zero"):
    reset_table(final_df)
else:
    display_table(final_df)
    display_table(final_df)
