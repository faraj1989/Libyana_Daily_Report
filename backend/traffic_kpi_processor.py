#!/usr/bin/env python3
"""
Libyana NPM - Traffic KPI Processor
Processes 2G, 3G, 4G traffic KPIs (per site and whole network).
"""

import os
import sys
import glob
import logging
from datetime import datetime
import pandas as pd

# Add parent directory to path for imports when running standalone
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.csv_loader import read_csv_skip_metadata
from backend.site_processor import find_file

logger = logging.getLogger(__name__)

# Traffic file patterns - updated to match actual file names
TRAFFIC_FILES = {
    '2G_Traffic': {
        'patterns': [
            '* (PS Traffic 2G).csv',
            '*(PS Traffic 2G).csv',
            '*PS Traffic 2G*.csv',
            '*PS Traffic 2G*.csv'
        ],
        'sheet_name': 'Traffic_2G',
        'site_col': 'eGBTS',
        'ps_col': 'PS Traffic(GB)',
        'cs_col': 'CS Traffic',
        'subnet_col': 'Subnet Name',
        'key_columns': ['Date', 'eGBTS']
    },
    '3G_Traffic': {
        'patterns': [
            '* (PS Traffic 3G).csv',
            '*(PS Traffic 3G).csv',
            '*PS Traffic 3G*.csv',
            '*PS Traffic 3G*.csv'
        ],
        'sheet_name': 'Traffic_3G',
        'site_col': 'NodeB',
        'ps_col': 'PS traffic (GB)',
        'cs_col': 'CS Traffic(Erl)',
        'subnet_col': 'Subnet Name',
        'key_columns': ['Date', 'NodeB']
    },
    '4G_Traffic': {
        'patterns': [
            '* (PS Traffic 4G).csv',
            '*(PS Traffic 4G).csv',
            '*PS Traffic 4G*.csv',
            '*PS Traffic 4G*.csv'
        ],
        'sheet_name': 'Traffic_4G',
        'site_col': 'eNodeB Name',
        'dl_col': 'Downlink Traffic Volume(GB)',
        'ul_col': 'UL Traffic Volume(GB)',
        'volte_col': 'VoLTE Traffic Volume (Erl)',
        'subnet_col': 'Subnet Name',
        'key_columns': ['Date', 'eNodeB Name']
    }
}


def process_traffic_kpis(day_folder, log_callback=None):
    """
    Process all 3 traffic files in the day folder.
    Returns a dictionary: sheet_name -> DataFrame
    """

    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    log("=" * 60)
    log("📊 PROCESSING TRAFFIC KPIs")
    log("=" * 60)

    results = {}

    for kpi_name, config in TRAFFIC_FILES.items():
        patterns = config['patterns']
        sheet_name = config['sheet_name']

        # Find the file
        file_path = find_file(day_folder, patterns)

        if file_path:
            log(f"📄 Processing {kpi_name}: {os.path.basename(file_path)}")
            try:
                df = read_csv_skip_metadata(file_path)
                if df is not None and not df.empty:
                    # Convert Date column to string for consistency
                    if 'Date' in df.columns:
                        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')

                    # Store config for later use
                    df.attrs['config'] = config
                    df.attrs['kpi_name'] = kpi_name

                    results[sheet_name] = df
                    log(f"   ✅ Loaded {len(df)} rows, {len(df.columns)} columns")
                    if 'Date' in df.columns:
                        dates = df['Date'].unique()
                        if len(dates) > 0:
                            log(f"   📅 Dates: {min(dates)} to {max(dates)}")
                else:
                    log(f"   ⚠️ File is empty or could not be read")
                    results[sheet_name] = None
            except Exception as e:
                log(f"   ❌ Error reading {kpi_name}: {e}")
                results[sheet_name] = None
        else:
            log(f"   ⚠️ No file found for {kpi_name}")
            results[sheet_name] = None

    log("=" * 60)
    return results


def aggregate_traffic_by_site(df, tech):
    """
    Aggregate traffic data by site per day.
    Returns a DataFrame with columns: Date, Site, Subnet Name, and traffic metrics.
    """
    if df is None or df.empty:
        return None

    config = df.attrs.get('config', {})
    site_col = config.get('site_col', 'Site')
    subnet_col = config.get('subnet_col', 'Subnet Name')

    # Determine which columns to aggregate based on technology
    if tech == '2G':
        ps_col = config.get('ps_col', 'PS Traffic(GB)')
        cs_col = config.get('cs_col', 'CS Traffic')

        agg_cols = {
            ps_col: 'sum',
            cs_col: 'sum'
        }
        group_cols = ['Date', site_col, subnet_col]
        rename_map = {
            site_col: 'Site',
            ps_col: '2G PS Traffic (GB)',
            cs_col: '2G CS Traffic (Erl)',
            subnet_col: 'Subnet Name'
        }

    elif tech == '3G':
        ps_col = config.get('ps_col', 'PS traffic (GB)')
        cs_col = config.get('cs_col', 'CS Traffic(Erl)')

        agg_cols = {
            ps_col: 'sum',
            cs_col: 'sum'
        }
        group_cols = ['Date', site_col, subnet_col]
        rename_map = {
            site_col: 'Site',
            ps_col: '3G PS Traffic (GB)',
            cs_col: '3G CS Traffic (Erl)',
            subnet_col: 'Subnet Name'
        }

    elif tech == '4G':
        dl_col = config.get('dl_col', 'Downlink Traffic Volume(GB)')
        ul_col = config.get('ul_col', 'UL Traffic Volume(GB)')
        volte_col = config.get('volte_col', 'VoLTE Traffic Volume (Erl)')

        # Create total traffic column
        if dl_col in df.columns and ul_col in df.columns:
            df['Total Traffic (GB)'] = df[dl_col] + df[ul_col]
            agg_cols = {
                dl_col: 'sum',
                ul_col: 'sum',
                'Total Traffic (GB)': 'sum',
            }
            if volte_col in df.columns:
                agg_cols[volte_col] = 'sum'
        else:
            agg_cols = {}
            if dl_col in df.columns:
                agg_cols[dl_col] = 'sum'
            if ul_col in df.columns:
                agg_cols[ul_col] = 'sum'
            if volte_col in df.columns:
                agg_cols[volte_col] = 'sum'

        group_cols = ['Date', site_col, subnet_col]
        rename_map = {
            site_col: 'Site',
            dl_col: '4G DL Traffic (GB)',
            ul_col: '4G UL Traffic (GB)',
            'Total Traffic (GB)': '4G PS Traffic (GB)',
            subnet_col: 'Subnet Name'
        }
        if volte_col in df.columns:
            rename_map[volte_col] = '4G VoLTE Traffic (Erl)'

        # Remove columns that don't exist
        rename_map = {k: v for k, v in rename_map.items() if k in agg_cols or k in ['Date', site_col, subnet_col]}

    # Group by date, site, subnet
    site_agg = df.groupby(group_cols).agg(agg_cols).reset_index()

    # Rename columns
    rename_map = {k: v for k, v in rename_map.items() if k in site_agg.columns}
    site_agg = site_agg.rename(columns=rename_map)

    return site_agg


def aggregate_traffic_whole_network(df, tech):
    """
    Aggregate traffic data for the whole network (all sites combined).
    Returns a DataFrame with columns: Date and aggregated traffic metrics.
    """
    if df is None or df.empty:
        return None

    config = df.attrs.get('config', {})

    # Determine which columns to aggregate based on technology
    if tech == '2G':
        ps_col = config.get('ps_col', 'PS Traffic(GB)')
        cs_col = config.get('cs_col', 'CS Traffic')

        agg_cols = {
            ps_col: 'sum',
            cs_col: 'sum'
        }
        rename_map = {
            ps_col: '2G PS Traffic (GB)',
            cs_col: '2G CS Traffic (Erl)'
        }

    elif tech == '3G':
        ps_col = config.get('ps_col', 'PS traffic (GB)')
        cs_col = config.get('cs_col', 'CS Traffic(Erl)')

        agg_cols = {
            ps_col: 'sum',
            cs_col: 'sum'
        }
        rename_map = {
            ps_col: '3G PS Traffic (GB)',
            cs_col: '3G CS Traffic (Erl)'
        }

    elif tech == '4G':
        dl_col = config.get('dl_col', 'Downlink Traffic Volume(GB)')
        ul_col = config.get('ul_col', 'UL Traffic Volume(GB)')
        volte_col = config.get('volte_col', 'VoLTE Traffic Volume (Erl)')

        if dl_col in df.columns and ul_col in df.columns:
            df['Total Traffic (GB)'] = df[dl_col] + df[ul_col]
            agg_cols = {
                dl_col: 'sum',
                ul_col: 'sum',
                'Total Traffic (GB)': 'sum',
            }
            if volte_col in df.columns:
                agg_cols[volte_col] = 'sum'
            rename_map = {
                dl_col: '4G DL Traffic (GB)',
                ul_col: '4G UL Traffic (GB)',
                'Total Traffic (GB)': '4G PS Traffic (GB)',
            }
            if volte_col in df.columns:
                rename_map[volte_col] = '4G VoLTE Traffic (Erl)'
        else:
            agg_cols = {}
            if dl_col in df.columns:
                agg_cols[dl_col] = 'sum'
            if ul_col in df.columns:
                agg_cols[ul_col] = 'sum'
            if volte_col in df.columns:
                agg_cols[volte_col] = 'sum'
            rename_map = {}
            if dl_col in df.columns:
                rename_map[dl_col] = '4G DL Traffic (GB)'
            if ul_col in df.columns:
                rename_map[ul_col] = '4G UL Traffic (GB)'
            if volte_col in df.columns:
                rename_map[volte_col] = '4G VoLTE Traffic (Erl)'

        rename_map = {k: v for k, v in rename_map.items() if k in agg_cols}

    # Group by date only
    network_agg = df.groupby('Date').agg(agg_cols).reset_index()

    # Rename columns
    rename_map = {k: v for k, v in rename_map.items() if k in network_agg.columns}
    network_agg = network_agg.rename(columns=rename_map)

    return network_agg


def process_traffic_with_aggregation(day_folder, log_callback=None):
    """
    Process traffic files and return both per-site and whole network aggregates.
    """

    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    log("=" * 60)
    log("📊 PROCESSING TRAFFIC WITH AGGREGATION")
    log("=" * 60)

    # Process raw traffic files
    raw_results = process_traffic_kpis(day_folder, log_callback)

    aggregated_results = {
        'per_site': {},
        'whole_network': {}
    }

    for sheet_name, df in raw_results.items():
        if df is not None and not df.empty:
            # Determine technology from sheet name
            tech = '2G' if '2G' in sheet_name else '3G' if '3G' in sheet_name else '4G'

            # Per-site aggregation
            site_agg = aggregate_traffic_by_site(df, tech)
            if site_agg is not None and not site_agg.empty:
                aggregated_results['per_site'][sheet_name] = site_agg
                log(f"   📊 {sheet_name} per-site: {len(site_agg)} rows, {len(site_agg.columns)} columns")

            # Whole network aggregation
            network_agg = aggregate_traffic_whole_network(df, tech)
            if network_agg is not None and not network_agg.empty:
                aggregated_results['whole_network'][sheet_name] = network_agg
                log(f"   📊 {sheet_name} whole network: {len(network_agg)} rows, {len(network_agg.columns)} columns")

    return aggregated_results


# ---------------------------- Test ----------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python traffic_kpi_processor.py <day_folder_path>")
        sys.exit(1)

    test_folder = sys.argv[1]

    # Test raw processing
    print("\n" + "=" * 60)
    print("TEST: RAW TRAFFIC PROCESSING")
    print("=" * 60)
    raw_results = process_traffic_kpis(test_folder)

    for sheet_name, df in raw_results.items():
        print(f"\n{sheet_name}:")
        if df is not None and not df.empty:
            print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
            if 'Date' in df.columns:
                dates = df['Date'].unique()
                print(f"  Date Range: {min(dates)} to {max(dates)}")
        else:
            print("  No data")

    # Test aggregated processing
    print("\n" + "=" * 60)
    print("TEST: AGGREGATED TRAFFIC PROCESSING")
    print("=" * 60)
    agg_results = process_traffic_with_aggregation(test_folder)

    print("\n--- Per Site ---")
    for sheet_name, df in agg_results['per_site'].items():
        if df is not None and not df.empty:
            print(f"{sheet_name}: {len(df)} rows, {len(df.columns)} columns")
            print(f"  Columns: {df.columns.tolist()[:8]}...")

    print("\n--- Whole Network ---")
    for sheet_name, df in agg_results['whole_network'].items():
        if df is not None and not df.empty:
            print(f"{sheet_name}: {len(df)} rows, {len(df.columns)} columns")
            print(f"  Columns: {df.columns.tolist()[:8]}...")