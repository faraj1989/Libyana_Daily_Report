#!/usr/bin/env python3
"""
Libyana NPM - Site Summary Processor
Step 2b: Process 2G, 3G, and 4G CSVs to count sites and band combinations.
"""

import os
import sys
import glob
import re
import logging
import argparse
from csv_loader import read_csv_skip_metadata

logger = logging.getLogger(__name__)

# 4G band mapping
SITE_SUMMARY_HEADER = [
    'day',
    '2G physical sites',
    '2G GSM900 Band',
    '2G DCS1800 Band',
    '2G 900 only',
    '2G 1800 only',
    '3G physical sites',
    '3G U2100 Band',
    '3G U900 Band',
    '3G U2100 only',
    '3G U900 only',
    '4G physical sites',
    '4G L1800 F1 Band',
    '4G L1800 F2 Band',
    '4G L2100 Band',
    '4G L900 Band',
    '4G L700 Band',
    '4G L1800 only',
    '4G L2100 only',
    '4G L900 only',
    '4G L700 only',
    'Total Physical Sites (2G+3G+4G)',
    '2G only sites',
    '3G only sites',
    '4G only sites',
    '2G+3G sites',
    '2G+4G sites',
    '3G+4G sites',
    '2G+3G+4G sites'
]


def extract_physical_name(name, tech):
    """
    Extract the physical site name from technology-specific naming.

    2G: 'BGZ001' -> 'BGZ001'
    3G: 'UBGZ001' -> 'BGZ001' (remove leading 'U')
    4G: 'BGZ001(FN)', 'BYDA023(FTTS)', 'BYDA019' -> 'BGZ001', 'BYDA023', 'BYDA019'
    """
    if tech == '2g':
        return name.strip()
    elif tech == '3g':
        # Remove leading 'U' if present
        if name.startswith('U'):
            return name[1:]
        return name
    elif tech == '4g':
        # Remove suffixes like (FN), (FTTS), (FTT), etc.
        # Also remove trailing spaces
        clean = re.sub(r'\s*\([^)]*\)$', '', name)
        return clean.strip()
    return name


def process_2g(df):
    """Return dict with 2G counts."""
    if df is None or df.empty:
        return {
            '2G physical sites': 0,
            '2G GSM900 Band': 0,
            '2G DCS1800 Band': 0,
            '2G 900 only': 0,
            '2G 1800 only': 0
        }

    site_col = 'Site Name'
    freq_col = 'DL frequency'

    unique_sites = df[site_col].unique()
    total = len(unique_sites)

    count_900 = 0
    count_1800 = 0
    count_900_only = 0
    count_1800_only = 0

    for site in unique_sites:
        freqs = df[df[site_col] == site][freq_col].unique()
        has_900 = any('900' in str(f).upper() for f in freqs)
        has_1800 = any('1800' in str(f).upper() for f in freqs)

        if has_900:
            count_900 += 1
        if has_1800:
            count_1800 += 1

        if has_900 and not has_1800:
            count_900_only += 1
        elif has_1800 and not has_900:
            count_1800_only += 1

    return {
        '2G physical sites': total,
        '2G GSM900 Band': count_900,
        '2G DCS1800 Band': count_1800,
        '2G 900 only': count_900_only,
        '2G 1800 only': count_1800_only
    }


def process_3g(df):
    """Return dict with 3G counts."""
    if df is None or df.empty:
        return {
            '3G physical sites': 0,
            '3G U2100 Band': 0,
            '3G U900 Band': 0,
            '3G U2100 only': 0,
            '3G U900 only': 0
        }

    nodeb_col = 'NodeB Name'
    band_col = 'Band Indicator'

    unique_nodebs = df[nodeb_col].unique()
    total = len(unique_nodebs)

    count_u2100 = 0
    count_u900 = 0
    count_u2100_only = 0
    count_u900_only = 0

    for nodeb in unique_nodebs:
        bands = df[df[nodeb_col] == nodeb][band_col].unique()
        has_u2100 = any('BAND1' in str(b).upper() for b in bands)
        has_u900 = any('BAND8' in str(b).upper() for b in bands)

        if has_u2100:
            count_u2100 += 1
        if has_u900:
            count_u900 += 1

        if has_u2100 and not has_u900:
            count_u2100_only += 1
        elif has_u900 and not has_u2100:
            count_u900_only += 1

    return {
        '3G physical sites': total,
        '3G U2100 Band': count_u2100,
        '3G U900 Band': count_u900,
        '3G U2100 only': count_u2100_only,
        '3G U900 only': count_u900_only
    }


def process_4g(df):
    """Return dict with 4G counts."""
    if df is None or df.empty:
        return {
            '4G physical sites': 0,
            '4G L1800 F1 Band': 0,
            '4G L1800 F2 Band': 0,
            '4G L2100 Band': 0,
            '4G L900 Band': 0,
            '4G L700 Band': 0,
            '4G L1800 only': 0,
            '4G L2100 only': 0,
            '4G L900 only': 0,
            '4G L700 only': 0
        }

    enb_col = 'eNodeB Name'
    band_col = ' Frequency band'  # NOTE: leading space!

    if enb_col not in df.columns or band_col not in df.columns:
        print(f"DEBUG: 4G - Could not find required columns.")
        print(f"DEBUG: Available columns: {df.columns.tolist()}")
        return {
            '4G physical sites': 0,
            '4G L1800 F1 Band': 0,
            '4G L1800 F2 Band': 0,
            '4G L2100 Band': 0,
            '4G L900 Band': 0,
            '4G L700 Band': 0,
            '4G L1800 only': 0,
            '4G L2100 only': 0,
            '4G L900 only': 0,
            '4G L700 only': 0
        }

    unique_enbs = df[enb_col].unique()
    total = len(unique_enbs)

    count_l1800 = 0
    count_l2100 = 0
    count_l900 = 0
    count_l700 = 0
    count_l1800_only = 0
    count_l2100_only = 0
    count_l900_only = 0
    count_l700_only = 0
    count_l1800_f2 = 0

    for enb in unique_enbs:
        # Get all rows for this eNodeB
        enb_data = df[df[enb_col] == enb]
        bands = enb_data[band_col].unique()
        band_set = set()
        for b in bands:
            try:
                band_set.add(int(b))
            except (ValueError, TypeError):
                pass

        has_l1800 = 3 in band_set
        has_l2100 = 1 in band_set
        has_l900 = 8 in band_set
        has_l700 = 28 in band_set

        if has_l1800:
            count_l1800 += 1
        if has_l2100:
            count_l2100 += 1
        if has_l900:
            count_l900 += 1
        if has_l700:
            count_l700 += 1

        # Check if site has both L1800 F1 and F2
        # F1 typically uses EARFCN 1401, F2 uses 1400
        if has_l1800:
            earfcns = enb_data['Downlink EARFCN'].unique()
            has_f1 = any(1400 <= e <= 1401 for e in earfcns if e is not None)
            has_f2 = any(1399 <= e <= 1400 for e in earfcns if e is not None)  # Adjust if different
            if has_f2:
                count_l1800_f2 += 1

        # Count only sites
        if len(band_set) == 1:
            if has_l1800:
                count_l1800_only += 1
            elif has_l2100:
                count_l2100_only += 1
            elif has_l900:
                count_l900_only += 1
            elif has_l700:
                count_l700_only += 1

    return {
        '4G physical sites': total,
        '4G L1800 F1 Band': count_l1800,
        '4G L1800 F2 Band': count_l1800_f2,
        '4G L2100 Band': count_l2100,
        '4G L900 Band': count_l900,
        '4G L700 Band': count_l700,
        '4G L1800 only': count_l1800_only,
        '4G L2100 only': count_l2100_only,
        '4G L900 only': count_l900_only,
        '4G L700 only': count_l700_only
    }


def get_physical_sites(df_2g, df_3g, df_4g):
    """
    Extract physical site names from all technologies and calculate overlaps.
    """
    physical_sites = {}
    site_sources = {
        '2g': set(),
        '3g': set(),
        '4g': set()
    }

    # Extract 2G physical sites
    if df_2g is not None and not df_2g.empty:
        for name in df_2g['Site Name'].unique():
            physical = extract_physical_name(name, '2g')
            physical_sites[physical] = physical_sites.get(physical, set())
            physical_sites[physical].add('2g')
            site_sources['2g'].add(physical)

    # Extract 3G physical sites
    if df_3g is not None and not df_3g.empty:
        for name in df_3g['NodeB Name'].unique():
            physical = extract_physical_name(name, '3g')
            physical_sites[physical] = physical_sites.get(physical, set())
            physical_sites[physical].add('3g')
            site_sources['3g'].add(physical)

    # Extract 4G physical sites
    if df_4g is not None and not df_4g.empty:
        for name in df_4g['eNodeB Name'].unique():
            physical = extract_physical_name(name, '4g')
            physical_sites[physical] = physical_sites.get(physical, set())
            physical_sites[physical].add('4g')
            site_sources['4g'].add(physical)

    # Calculate overlaps
    total_physical = len(physical_sites)

    # Count by combination
    count_2g_only = 0
    count_3g_only = 0
    count_4g_only = 0
    count_2g_3g = 0
    count_2g_4g = 0
    count_3g_4g = 0
    count_all_three = 0

    for site, techs in physical_sites.items():
        if techs == {'2g'}:
            count_2g_only += 1
        elif techs == {'3g'}:
            count_3g_only += 1
        elif techs == {'4g'}:
            count_4g_only += 1
        elif techs == {'2g', '3g'}:
            count_2g_3g += 1
        elif techs == {'2g', '4g'}:
            count_2g_4g += 1
        elif techs == {'3g', '4g'}:
            count_3g_4g += 1
        elif techs == {'2g', '3g', '4g'}:
            count_all_three += 1

    return {
        'Total Physical Sites (2G+3G+4G)': total_physical,
        '2G only sites': count_2g_only,
        '3G only sites': count_3g_only,
        '4G only sites': count_4g_only,
        '2G+3G sites': count_2g_3g,
        '2G+4G sites': count_2g_4g,
        '3G+4G sites': count_3g_4g,
        '2G+3G+4G sites': count_all_three
    }


def find_file(folder, patterns):
    """Search for a file matching any of the given patterns."""
    for pattern in patterns:
        full_pattern = os.path.join(folder, pattern)
        matches = glob.glob(full_pattern)
        if matches:
            return matches[0]
    return None


def process_site_day(day_folder):
    """Process all three CSVs and return a summary dictionary."""
    # List all files for debugging
    all_files = glob.glob(os.path.join(day_folder, '*.csv'))
    print(f"DEBUG: Found {len(all_files)} CSV files in folder:")
    for f in all_files:
        print(f"  {os.path.basename(f)}")

    # Patterns for each technology
    patterns_2g = ['* (2G).csv', '*(2G).csv', '*2G*.csv']
    patterns_3g = ['* (3G).csv', '*(3G).csv', '*3G*.csv']
    patterns_4g = ['* (4G).csv', '*(4G).csv', '*4G*.csv']

    file_2g = find_file(day_folder, patterns_2g)
    file_3g = find_file(day_folder, patterns_3g)
    file_4g = find_file(day_folder, patterns_4g)

    site_row = {}

    df_2g = None
    df_3g = None
    df_4g = None

    if file_2g:
        print(f"DEBUG: Using 2G file: {os.path.basename(file_2g)}")
        df_2g = read_csv_skip_metadata(file_2g)
        site_row.update(process_2g(df_2g))
    else:
        print("DEBUG: No 2G file found.")
        site_row.update(process_2g(None))

    if file_3g:
        print(f"DEBUG: Using 3G file: {os.path.basename(file_3g)}")
        df_3g = read_csv_skip_metadata(file_3g)
        site_row.update(process_3g(df_3g))
    else:
        print("DEBUG: No 3G file found.")
        site_row.update(process_3g(None))

    if file_4g:
        print(f"DEBUG: Using 4G file: {os.path.basename(file_4g)}")
        df_4g = read_csv_skip_metadata(file_4g)
        site_row.update(process_4g(df_4g))
    else:
        print("DEBUG: No 4G file found.")
        site_row.update(process_4g(None))

    # Get physical site overlaps
    physical_counts = get_physical_sites(df_2g, df_3g, df_4g)
    site_row.update(physical_counts)

    # Ensure all columns exist (fill missing with 0)
    for col in SITE_SUMMARY_HEADER:
        if col not in site_row:
            site_row[col] = 0

    return site_row


# ---------------------------- Main ----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process site summary for a given day folder.')
    parser.add_argument('--folder', help='Path to the unzipped folder containing the CSVs', required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if not os.path.exists(args.folder):
        print(f"Error: Folder not found: {args.folder}")
        sys.exit(1)

    result = process_site_day(args.folder)
    print("\nSite Summary Result:")
    print("=" * 50)
    for key, value in result.items():
        print(f"{key}: {value}")