import streamlit as st
try:
response = requests.get(API_URL, params={'_ts': int(time.time())}, timeout=20)
response.raise_for_status()
df = pd.DataFrame(response.json())


st.sidebar.header("FILTERS")
sheet_filter = st.sidebar.selectbox("DEPARTMENT", options=sorted(df["SOURCE_SHEET"].unique().tolist()))
client_filter = st.sidebar.text_input("CLIENT NAME")
client_code_input = st.sidebar.text_input("Enter Client Code to Edit")


# Filter
filtered_df = df[df["SOURCE_SHEET"] == sheet_filter].copy()
if client_filter:
filtered_df = filtered_df[filtered_df["CLIENT NAME"].str.contains(client_filter, case=False, na=False)]


# Candidate columns per sheet (these are patterns — actual headers in Excel may contain punctuation)
candidates_map = {
"SS": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE", "PERSONAL LINES", "AFFINITY", "EMPLOYEE BENEFITS"],
"corp": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "EMPLOYEE BENEFITS", "PERSONAL LINES", "STAFF SCHEMES"],
"EB": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE", "AFFINITY", "STAFF SCHEMES", "PERSONAL LINES"],
"PLD": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "CORPORATE", "STAFF SCHEMES", "EMPLOYEE BENEFITS", "AFFINITY", "MINING"],
"AFFINITY": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "EMPLOYEE BENEFITS", "STAFF SCHEMES", "PERSONAL LINES"],
"MINING": ["CLIENT CODE", "CLIENT NAME", "PREMIUM", "EMPLOYEE BENEFITS", "AFFINITY", "STAFF SCHEMES", "PERSONAL LINES"]
}


candidates = candidates_map.get(sheet_filter, filtered_df.columns.tolist())
columns_to_show = build_columns_to_show(filtered_df, candidates)
if not columns_to_show:
columns_to_show = filtered_df.columns.tolist()


display_df = filtered_df[columns_to_show]


if client_code_input:
display_df = display_df[display_df[find_matching_column(display_df.columns, 'CLIENT CODE')].astype(str).str.strip().str.lower() == (client_code_input or '').strip().lower()]


# Format premium columns
for col in display_df.columns:
if 'PREMIUM' in canonicalize(col):
def fmt(x):
try:
return f"{float(x):,.2f}" if pd.notnull(x) else ''
except Exception:
return x
display_df[col] = display_df[col].apply(fmt)


# Highlight cross-sell
def highlight_cross_sell(val):
return 'color: red; font-weight: bold;' if str(val).strip().lower() == 'cross-sell' else ''


styled_df = display_df.style.applymap(highlight_cross_sell).hide(axis='index')
st.markdown(f"<div class='scroll-container'>{styled_df.to_html()}</div>", unsafe_allow_html=True)


# Edit section
if client_code_input:
if display_df.empty:
st.warning('No client found with that code.')
else:
st.markdown('### Edit Client Details')
editable_cols = [col for col in display_df.columns if canonicalize(col) not in ['CLIENT CODE', 'CLIENT NAME']]
selected_col = st.selectbox('Select Column to Edit', options=editable_cols)
new_value_option = st.selectbox('Select New Value', options=['Cross-Sell', 'Shared Client'])
final_value = new_value_option


if st.button('Apply Change'):
# IMPORTANT: send the actual column header name as found in the dataframe (not further canonicalized)
payload = {
'sheet': sheet_filter,
'client_code': (client_code_input or '').strip(),
'column': selected_col, # send the exact header text
'new_value': final_value
}
try:
update_response = requests.post(UPDATE_URL, json=payload, timeout=20)
if update_response.status_code == 200:
except Exc
