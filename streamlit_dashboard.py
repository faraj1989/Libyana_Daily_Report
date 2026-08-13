#!/usr/bin/env python3
"""
Libyana NPM - Complete Streamlit Dashboard (SMART FALLBACK)
Shows latest available data when selected date has no data
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime
import numpy as np

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Libyana Network Dashboard",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    .header-container {
        background: linear-gradient(90deg, #1f77b4, #17becf);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 20px;
    }
    .fallback-note {
        color: #ff7f0e;
        font-size: 12px;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATE NORMALIZATION
# ============================================================
def normalize_date(date_str):
    """Convert any date format to YYYY-MM-DD"""
    if date_str is None:
        return None
    if pd.isna(date_str):
        return None
    try:
        date_str = str(date_str).strip()
        dt = pd.to_datetime(date_str)
        return dt.strftime('%Y-%m-%d')
    except:
        return date_str


# ============================================================
# HEADER
# ============================================================
st.markdown("""
<div class="header-container">
    <h1 style="margin:0;">📊 Libyana Network Performance Dashboard</h1>
    <p style="margin:0;">EAST Region | Real-time Network Monitoring</p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# FIND DATA
# ============================================================
def find_data():
    possible_paths = ["output/csv", "output/csv/", "output", "."]
    for path in possible_paths:
        if os.path.exists(path):
            site_file = os.path.join(path, "SiteSummary.csv")
            if os.path.exists(site_file):
                return path
    return None


data_path = find_data()

if data_path is None:
    st.error("❌ No data found! Please run the main GUI first to generate CSV files.")
    st.stop()


# ============================================================
# LOAD DATA
# ============================================================
@st.cache_data(ttl=3600)
def load_csv_files(folder_path):
    data = {}
    csv_files = {
        'SiteSummary': 'SiteSummary.csv',
        'User_Summary': 'User_Summary.csv',
        '4G_NWBH': '4G_NWBH.csv',
        '4G_NW_Daily': '4G_NW_Daily.csv',
        '3G_NWBH': '3G_NWBH.csv',
        '3G_NW_Daily': '3G_NW_Daily.csv',
        '2G_NWBH': '2G_NWBH.csv',
        '2G_NW_Daily': '2G_NW_Daily.csv',
        'Traffic_Network_2G': 'Traffic_Network_2G.csv',
        'Traffic_Network_3G': 'Traffic_Network_3G.csv',
        'Traffic_Network_4G': 'Traffic_Network_4G.csv',
    }
    for key, filename in csv_files.items():
        filepath = os.path.join(folder_path, filename)
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath)
                if not df.empty:
                    data[key] = df
            except Exception as e:
                print(f"⚠️ Error loading {key}: {e}")
    return data


with st.spinner("📊 Loading data..."):
    data = load_csv_files(data_path)

if not data:
    st.error("❌ No data loaded!")
    st.stop()

# ============================================================
# GET DATES PER SHEET
# ============================================================
date_info = {}

if 'SiteSummary' in data and 'day' in data['SiteSummary'].columns:
    dates = sorted(data['SiteSummary']['day'].unique(), reverse=True)
    date_info['SiteSummary'] = [normalize_date(d) for d in dates]

if 'User_Summary' in data and 'Date' in data['User_Summary'].columns:
    dates = sorted(data['User_Summary']['Date'].unique(), reverse=True)
    date_info['User_Summary'] = [normalize_date(d) for d in dates]

if '4G_NWBH' in data and 'Date' in data['4G_NWBH'].columns:
    dates = sorted(data['4G_NWBH']['Date'].unique(), reverse=True)
    date_info['4G_NWBH'] = [normalize_date(d) for d in dates]

if '4G_NW_Daily' in data and 'Date' in data['4G_NW_Daily'].columns:
    dates = sorted(data['4G_NW_Daily']['Date'].unique(), reverse=True)
    date_info['4G_NW_Daily'] = [normalize_date(d) for d in dates]

if '3G_NWBH' in data and 'Date' in data['3G_NWBH'].columns:
    dates = sorted(data['3G_NWBH']['Date'].unique(), reverse=True)
    date_info['3G_NWBH'] = [normalize_date(d) for d in dates]

if '2G_NWBH' in data and 'Date' in data['2G_NWBH'].columns:
    dates = sorted(data['2G_NWBH']['Date'].unique(), reverse=True)
    date_info['2G_NWBH'] = [normalize_date(d) for d in dates]

# Get all unique dates
all_dates = set()
for dates in date_info.values():
    all_dates.update(dates)
all_dates = sorted(all_dates, reverse=True)

if not all_dates:
    st.error("❌ No dates found!")
    st.stop()


# ============================================================
# HELPERS WITH SMART FALLBACK
# ============================================================
def get_row_with_fallback(df, date_col, date_str, show_fallback_msg=True):
    """
    Get row matching date.
    Returns: (row, is_exact_match, actual_date)
    """
    if df is None or date_col not in df.columns:
        return None, False, None

    try:
        target_date = normalize_date(date_str)
        df_dates = df[date_col].apply(normalize_date)
        rows = df[df_dates == target_date]

        if not rows.empty:
            return rows.iloc[0], True, target_date

        # Fallback: get latest available
        df_copy = df.copy()
        df_copy['_normalized_date'] = df_copy[date_col].apply(normalize_date)
        df_sorted = df_copy.sort_values('_normalized_date', ascending=False)
        if not df_sorted.empty:
            row = df_sorted.iloc[0]
            actual_date = row.get(date_col, 'N/A')
            actual_date = normalize_date(actual_date)
            return row, False, actual_date
    except Exception as e:
        print(f"Error in get_row_with_fallback: {e}")

    return None, False, None


def get_latest_row(df, date_col):
    if df is None or date_col not in df.columns:
        return None
    try:
        df_copy = df.copy()
        df_copy['_normalized_date'] = df_copy[date_col].apply(normalize_date)
        df_sorted = df_copy.sort_values('_normalized_date', ascending=False)
        return df_sorted.iloc[0] if not df_sorted.empty else None
    except:
        return None


def get_last_n_days(df, date_col, n=14):
    if df is None or date_col not in df.columns:
        return None
    try:
        df_copy = df.copy()
        df_copy['_normalized_date'] = df_copy[date_col].apply(normalize_date)
        df_sorted = df_copy.sort_values('_normalized_date', ascending=False)
        return df_sorted.head(n).sort_values('_normalized_date', ascending=True)
    except:
        return None


def format_number(value):
    try:
        return f"{int(value):,}"
    except:
        return str(value)


def format_float(value, decimals=2):
    try:
        return f"{float(value):.{decimals}f}"
    except:
        return "0.00"


def format_traffic(value):
    try:
        return f"{float(value):,.2f}"
    except:
        return "0.00"


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("📅 Controls")

    display_dates = []
    for d in all_dates:
        try:
            dt = pd.to_datetime(d)
            display_dates.append(dt.strftime('%m/%d/%Y'))
        except:
            display_dates.append(d)

    selected_display = st.selectbox("Choose a date:", display_dates, index=0)

    try:
        selected_date = pd.to_datetime(selected_display).strftime('%Y-%m-%d')
    except:
        selected_date = selected_display

    st.caption(f"📊 Total days: {len(all_dates)}")

    st.divider()
    st.subheader("📁 Data Availability")
    for sheet, dates in date_info.items():
        if selected_date in dates:
            st.caption(f"  ✅ {sheet}: {selected_date}")
        else:
            latest = dates[0] if dates else "N/A"
            st.caption(f"  ⚠️ {sheet}: latest {latest}")

# ============================================================
# GET DATA FOR SELECTED DATE (WITH FALLBACK)
# ============================================================
site_row, site_exact, site_actual = get_row_with_fallback(data.get('SiteSummary'), 'day', selected_date)
user_row, user_exact, user_actual = get_row_with_fallback(data.get('User_Summary'), 'Date', selected_date)
nw_4g_row, nw_4g_exact, nw_4g_actual = get_row_with_fallback(data.get('4G_NWBH'), 'Date', selected_date)
traffic_2g_row, traffic_2g_exact, traffic_2g_actual = get_row_with_fallback(data.get('Traffic_Network_2G'), 'Date',
                                                                            selected_date)
traffic_3g_row, traffic_3g_exact, traffic_3g_actual = get_row_with_fallback(data.get('Traffic_Network_3G'), 'Date',
                                                                            selected_date)
traffic_4g_row, traffic_4g_exact, traffic_4g_actual = get_row_with_fallback(data.get('Traffic_Network_4G'), 'Date',
                                                                            selected_date)

has_site_data = site_row is not None
has_user_data = user_row is not None
has_nw_4g_data = nw_4g_row is not None
has_traffic_2g = traffic_2g_row is not None
has_traffic_3g = traffic_3g_row is not None
has_traffic_4g = traffic_4g_row is not None


# ============================================================
# CALCULATE KPIs
# ============================================================
def calculate_kpis():
    kpis = {}
    if user_row is not None:
        ps_2g = user_row.get('2G PS user', 0)
        ps_3g = user_row.get('3G PS user', 0)
        ps_4g = user_row.get('4G PS user', 0)
        kpis['total_ps_users'] = ps_2g + ps_3g + ps_4g
        kpis['lte_max_users'] = ps_4g
        kpis['volte_users'] = user_row.get('VoLTE user', 0)
        kpis['cs_roaming'] = user_row.get('Roaming CS (Almadar)', 0)
        cs_2g = user_row.get('2G CS user', 0)
        cs_3g = user_row.get('3G CS user', 0)
        kpis['cs_subscribers'] = cs_2g + cs_3g
    else:
        kpis['total_ps_users'] = 0
        kpis['lte_max_users'] = 0
        kpis['volte_users'] = 0
        kpis['cs_roaming'] = 0
        kpis['cs_subscribers'] = 0

    if traffic_2g_row is not None:
        kpis['traffic_2g_ps'] = traffic_2g_row.get('2G PS Traffic (GB)', 0)
        kpis['traffic_2g_cs'] = traffic_2g_row.get('2G CS Traffic (Erl)', 0)
    else:
        kpis['traffic_2g_ps'] = 0
        kpis['traffic_2g_cs'] = 0

    if traffic_3g_row is not None:
        kpis['traffic_3g_ps'] = traffic_3g_row.get('3G PS Traffic (GB)', 0)
        kpis['traffic_3g_cs'] = traffic_3g_row.get('3G CS Traffic (Erl)', 0)
    else:
        kpis['traffic_3g_ps'] = 0
        kpis['traffic_3g_cs'] = 0

    if traffic_4g_row is not None:
        kpis['traffic_4g_ps'] = traffic_4g_row.get('4G DL Traffic (GB)', 0)
        kpis['traffic_4g_volte'] = traffic_4g_row.get('4G VoLTE Traffic (Erl)', 0)
    else:
        kpis['traffic_4g_ps'] = 0
        kpis['traffic_4g_volte'] = 0

    kpis['total_ps_traffic'] = kpis['traffic_2g_ps'] + kpis['traffic_3g_ps'] + kpis['traffic_4g_ps']
    kpis['lte_traffic'] = kpis['traffic_4g_ps']
    kpis['total_cs_traffic'] = kpis['traffic_2g_cs'] + kpis['traffic_3g_cs']

    if nw_4g_row is not None:
        kpis['packet_loss'] = nw_4g_row.get('Downlink Packet Loss', 0)
        kpis['rrc_setup_success'] = nw_4g_row.get('RRC Setup Success Rate(%)', 0)
        kpis['erab_setup_success'] = nw_4g_row.get('E-RAB Setup Success Rate', 0)
        kpis['network_availability'] = nw_4g_row.get('Radio Network Availability Rate(%)', 0)
        kpis['lte_user_throughput'] = nw_4g_row.get('User Downlink Average Throughput (Mbps)', 0)
        kpis['volte_cssr'] = nw_4g_row.get('VoLTE Setup Success Rate-ZM(%)', 0)
        kpis['service_drop_rate'] = nw_4g_row.get('Service Drop Rate (All)', 0)
    else:
        kpis['packet_loss'] = 0
        kpis['rrc_setup_success'] = 0
        kpis['erab_setup_success'] = 0
        kpis['network_availability'] = 0
        kpis['lte_user_throughput'] = 0
        kpis['volte_cssr'] = 0
        kpis['service_drop_rate'] = 0

    if kpis['traffic_4g_ps'] > 0:
        kpis['total_throughput'] = (kpis['traffic_4g_ps'] * 8) / 3600
        kpis['lte_dl_throughput'] = (kpis['traffic_4g_ps'] * 8) / 3600
    else:
        kpis['total_throughput'] = 0
        kpis['lte_dl_throughput'] = 0

    return kpis


kpis = calculate_kpis()


# ============================================================
# GENERATE EMAIL REPORT
# ============================================================
def generate_email_report():
    lines = []
    lines.append("=" * 70)
    lines.append(f"📊 LIBYANA NETWORK PERFORMANCE REPORT")
    lines.append("=" * 70)

    # Show actual dates used (with fallback notes)
    date_note = selected_date
    if not site_exact and site_actual:
        date_note = f"{selected_date} (Site data from {site_actual})"
    lines.append(f"Date: {date_note}")
    lines.append(f"Region: EAST")
    lines.append("=" * 70)
    lines.append("")
    lines.append("📈 NETWORK SUMMARY:")
    lines.append("-" * 50)
    lines.append(f"• Total PS users (2G+3G+4G)         : {format_number(kpis['total_ps_users'])}")
    lines.append(f"• Total PS traffic                  : {format_float(kpis['total_ps_traffic'])} GB")
    lines.append(f"• CS subscribers (2G+3G)            : {format_number(kpis['cs_subscribers'])}")
    lines.append(f"• Total CS traffic (2G+3G)          : {format_float(kpis['total_cs_traffic'])} Erlangs")
    lines.append(f"• LTE maximum attached users        : {format_number(kpis['lte_max_users'])}")
    lines.append(f"• Total LTE traffic                 : {format_float(kpis['lte_traffic'])} GB")
    lines.append(f"• Maximum number of VoLTE users     : {format_number(kpis['volte_users'])}")
    lines.append(f"• Number of CS roaming users        : {format_number(kpis['cs_roaming'])}")
    lines.append(f"• Average ping packet loss rate     : {format_float(kpis['packet_loss'], 4)}")
    lines.append(f"• RRC Setup Success Rate (%)        : {format_float(kpis['rrc_setup_success'], 4)}")
    lines.append(f"• E-RAB Setup Success Rate (%)      : {format_float(kpis['erab_setup_success'], 4)}")
    lines.append(f"• LTE DL throughput                 : {format_float(kpis['lte_dl_throughput'], 2)} Gb/s")
    lines.append(f"• Average LTE user DL throughput    : {format_float(kpis['lte_user_throughput'], 3)} Mbps")
    lines.append(f"• VoLTE setup success rate (%)      : {format_float(kpis['volte_cssr'], 3)}")
    lines.append(f"• Service drop rate (%)             : {format_float(kpis['service_drop_rate'], 3)}")

    # Add fallback notes if any
    if not site_exact and site_actual:
        lines.append("")
        lines.append(f"ℹ️ Note: Site data from {site_actual} (no data for {selected_date})")

    lines.append("")
    lines.append("-" * 70)
    lines.append("")
    lines.append("Best Regards,")
    lines.append("")
    lines.append("Faraj Ramadan Elshahaibi")
    lines.append("RF Team Leader")
    lines.append("____________________________")
    lines.append("Network Optimization Engineer / East Area")
    lines.append("Network Operation Department / East Area")
    lines.append("Libyana Mobile Phone")
    lines.append("Benghazi - Libya")
    lines.append("📱 +218 94 7776248")
    lines.append("")
    lines.append("=" * 70)
    lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    return "\n".join(lines)


# ============================================================
# CREATE CHARTS FUNCTION
# ============================================================
def create_line_charts(df, date_col, columns, chart_prefix, cols_per_row=2):
    if df is None or df.empty:
        return

    df_last = get_last_n_days(df, date_col, 14)
    if df_last is None or df_last.empty:
        return

    num_cols = len(columns)
    rows = (num_cols + cols_per_row - 1) // cols_per_row
    chart_counter = 0

    for row in range(rows):
        cols = st.columns(cols_per_row)
        for col_idx in range(cols_per_row):
            idx = row * cols_per_row + col_idx
            if idx >= num_cols:
                break

            col_name = columns[idx]
            if col_name not in df_last.columns:
                with cols[col_idx]:
                    st.warning(f"Column {col_name} not found")
                continue

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_last[date_col],
                y=df_last[col_name],
                mode='lines+markers',
                name=col_name,
                line=dict(width=2),
                marker=dict(size=6)
            ))

            fig.update_layout(
                title=col_name,
                xaxis_title='Date',
                yaxis_title=col_name,
                height=250,
                margin=dict(l=40, r=20, t=40, b=40),
                showlegend=False,
                hovermode='x unified'
            )

            with cols[col_idx]:
                st.plotly_chart(fig, key=f"{chart_prefix}_{row}_{col_idx}_{chart_counter}", width='stretch')
                chart_counter += 1


# ============================================================
# MAIN DASHBOARD
# ============================================================
# Show date note if using fallback
if not site_exact and site_actual:
    st.info(f"ℹ️ Site data is from {site_actual} (no data for {selected_date})")

main_tab, tab_4g, tab_3g, tab_2g = st.tabs([
    "📊 Main Summary",
    "📱 4G Network",
    "📱 3G Network",
    "📱 2G Network"
])

# ============================================================
# MAIN TAB
# ============================================================
with main_tab:
    st.subheader(f"📊 Network Summary - {selected_date}")

    if not site_exact and site_actual:
        st.caption(f"ℹ️ Using site data from: {site_actual}")

    if has_site_data:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏗️ Total Sites", format_number(site_row.get('Total Physical Sites (2G+3G+4G)', 0)))
        with col2:
            st.metric("📶 2G Sites", format_number(site_row.get('2G physical sites', 0)))
        with col3:
            st.metric("📶 3G Sites", format_number(site_row.get('3G physical sites', 0)))
        with col4:
            st.metric("📶 4G Sites", format_number(site_row.get('4G physical sites', 0)))
    else:
        st.warning("⚠️ No site data available")

    st.subheader("👥 User KPIs")
    if has_user_data:
        if not user_exact and user_actual:
            st.caption(f"ℹ️ Using user data from: {user_actual}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total PS Users", format_number(kpis['total_ps_users']))
        with col2:
            st.metric("VoLTE Users", format_number(kpis['volte_users']))
        with col3:
            st.metric("CS Roaming", format_number(kpis['cs_roaming']))
        with col4:
            st.metric("CS Subscribers", format_number(kpis['cs_subscribers']))

        col5, col6, col7, col8 = st.columns(4)
        with col5:
            st.metric("2G PS Users", format_number(user_row.get('2G PS user', 0)))
        with col6:
            st.metric("3G PS Users", format_number(user_row.get('3G PS user', 0)))
        with col7:
            st.metric("4G PS Users", format_number(user_row.get('4G PS user', 0)))
        with col8:
            st.metric("Total VLR", format_number(user_row.get('Total VLR Subscribers', 0)))
    else:
        st.warning("⚠️ No user data available")

    st.subheader("📶 4G Network KPIs")
    if has_nw_4g_data:
        if not nw_4g_exact and nw_4g_actual:
            st.caption(f"ℹ️ Using 4G data from: {nw_4g_actual}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("RRC Setup Success", f"{format_float(kpis['rrc_setup_success'])}%")
        with col2:
            st.metric("E-RAB Setup Success", f"{format_float(kpis['erab_setup_success'])}%")
        with col3:
            st.metric("Service Drop Rate", f"{format_float(kpis['service_drop_rate'], 3)}%")
        with col4:
            st.metric("Network Availability", f"{format_float(kpis['network_availability'])}%")

        col5, col6, col7 = st.columns(3)
        with col5:
            st.metric("DL Throughput", f"{format_float(kpis['lte_user_throughput'], 3)} Mbps")
        with col6:
            st.metric("VoLTE CSSR", f"{format_float(kpis['volte_cssr'])}%")
        with col7:
            st.metric("Packet Loss", f"{format_float(kpis['packet_loss'], 4)}")
    else:
        st.warning("⚠️ No 4G network data available")

    st.subheader("📊 Traffic Summary")

    # Show traffic fallback notes
    if not traffic_2g_exact and traffic_2g_actual:
        st.caption(f"ℹ️ 2G traffic from: {traffic_2g_actual}")
    if not traffic_3g_exact and traffic_3g_actual:
        st.caption(f"ℹ️ 3G traffic from: {traffic_3g_actual}")
    if not traffic_4g_exact and traffic_4g_actual:
        st.caption(f"ℹ️ 4G traffic from: {traffic_4g_actual}")

    col1, col2, col3 = st.columns(3)
    with col1:
        if has_traffic_2g:
            st.metric("2G PS Traffic", f"{format_traffic(kpis['traffic_2g_ps'])} GB")
            st.metric("2G CS Traffic", f"{format_traffic(kpis['traffic_2g_cs'])} Erl")
        else:
            st.metric("2G PS Traffic", "No data")
            st.metric("2G CS Traffic", "No data")
    with col2:
        if has_traffic_3g:
            st.metric("3G PS Traffic", f"{format_traffic(kpis['traffic_3g_ps'])} GB")
            st.metric("3G CS Traffic", f"{format_traffic(kpis['traffic_3g_cs'])} Erl")
        else:
            st.metric("3G PS Traffic", "No data")
            st.metric("3G CS Traffic", "No data")
    with col3:
        if has_traffic_4g:
            st.metric("4G DL Traffic", f"{format_traffic(kpis['traffic_4g_ps'])} GB")
            st.metric("4G VoLTE Traffic", f"{format_traffic(kpis['traffic_4g_volte'])} Erl")
        else:
            st.metric("4G DL Traffic", "No data")
            st.metric("4G VoLTE Traffic", "No data")

    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📧 Generate Email Report", type="primary", use_container_width=True):
            email_text = generate_email_report()
            st.subheader("📧 Email Report - Copy and Paste")
            st.text_area("Email Content", email_text, height=500)
            st.success("✅ Report generated! Select all text and press Ctrl+C to copy")

# ============================================================
# 4G/3G/2G TABS - Keep the same as before
# ============================================================
# ... (the 4G, 3G, 2G tab code remains the same as the previous version)