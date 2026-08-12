# debug_all_dates.py
"""
Debug script to check date formats and latest dates in all CSV files
"""

import pandas as pd
import os
import glob
from datetime import datetime


def check_dates_in_csv(filepath):
    """Check date column in a CSV file"""
    results = {
        'file': os.path.basename(filepath),
        'exists': True,
        'rows': 0,
        'date_col': None,
        'date_format': None,
        'dates': [],
        'latest_date': None,
        'earliest_date': None,
        'date_range': None,
        'error': None
    }

    try:
        df = pd.read_csv(filepath)
        results['rows'] = len(df)

        if df.empty:
            results['error'] = "File is empty"
            return results

        # Find date column
        date_col = None
        for col in df.columns:
            if col.lower() in ['date', 'day', 'time']:
                date_col = col
                break

        if date_col is None:
            # Try to find any column that looks like dates
            for col in df.columns:
                sample = df[col].head(3).dropna()
                if len(sample) > 0:
                    try:
                        pd.to_datetime(sample.iloc[0])
                        date_col = col
                        break
                    except:
                        pass

        if date_col is None:
            results['error'] = "No date column found"
            return results

        results['date_col'] = date_col

        # Parse dates
        parsed_dates = []
        date_formats = []

        for val in df[date_col].head(10):
            if pd.isna(val):
                continue
            val_str = str(val).strip()

            # Try different formats
            formats_tried = []

            # YYYY-MM-DD
            try:
                dt = pd.to_datetime(val_str, format='%Y-%m-%d')
                parsed_dates.append(dt)
                date_formats.append('YYYY-MM-DD')
                continue
            except:
                pass

            # MM/DD/YYYY
            try:
                dt = pd.to_datetime(val_str, format='%m/%d/%Y')
                parsed_dates.append(dt)
                date_formats.append('MM/DD/YYYY')
                continue
            except:
                pass

            # M/D/YYYY
            try:
                dt = pd.to_datetime(val_str, format='%m/%d/%Y')
                parsed_dates.append(dt)
                date_formats.append('M/D/YYYY')
                continue
            except:
                pass

            # DD/MM/YYYY
            try:
                dt = pd.to_datetime(val_str, format='%d/%m/%Y')
                parsed_dates.append(dt)
                date_formats.append('DD/MM/YYYY')
                continue
            except:
                pass

            # Generic
            try:
                dt = pd.to_datetime(val_str)
                parsed_dates.append(dt)
                date_formats.append('Auto-detected')
                continue
            except:
                pass

        # Get all dates
        all_dates = []
        for val in df[date_col]:
            if pd.isna(val):
                continue
            try:
                dt = pd.to_datetime(val)
                all_dates.append(dt)
            except:
                pass

        if all_dates:
            results['dates'] = sorted(all_dates)
            results['latest_date'] = max(all_dates).strftime('%Y-%m-%d')
            results['earliest_date'] = min(all_dates).strftime('%Y-%m-%d')
            results['date_range'] = f"{results['earliest_date']} to {results['latest_date']}"

            # Detect format
            if date_formats:
                format_counts = {}
                for f in date_formats:
                    format_counts[f] = format_counts.get(f, 0) + 1
                results['date_format'] = max(format_counts, key=format_counts.get)

    except Exception as e:
        results['error'] = str(e)

    return results


def main():
    print("=" * 70)
    print("🔍 DEBUG: CHECKING ALL CSV FILES IN output/csv/")
    print("=" * 70)
    print()

    csv_folder = "output/csv"

    if not os.path.exists(csv_folder):
        print(f"❌ Folder not found: {csv_folder}")
        print(f"   Current directory: {os.getcwd()}")
        return

    # Get all CSV files
    csv_files = glob.glob(os.path.join(csv_folder, "*.csv"))

    if not csv_files:
        print(f"❌ No CSV files found in {csv_folder}")
        return

    print(f"📁 Found {len(csv_files)} CSV files\n")

    # Check each file
    all_results = []

    for filepath in sorted(csv_files):
        result = check_dates_in_csv(filepath)
        all_results.append(result)

        # Print summary
        status = "✅" if result['error'] is None else "❌"
        print(f"{status} {result['file']}")
        print(f"   Rows: {result['rows']}")

        if result['error']:
            print(f"   ⚠️ Error: {result['error']}")
        else:
            print(f"   Date Column: {result['date_col']}")
            print(f"   Format: {result['date_format']}")
            if result['latest_date']:
                print(f"   Date Range: {result['date_range']}")
                print(f"   Latest: {result['latest_date']}")
        print()

    # Summary - files with dates
    print("=" * 70)
    print("📊 SUMMARY - LATEST DATE PER FILE")
    print("=" * 70)
    print()

    print("| File Name | Latest Date | Date Format | Rows |")
    print("|-----------|-------------|-------------|------|")

    for result in all_results:
        if result['error'] is None and result['latest_date']:
            latest = result['latest_date']
            format_str = result['date_format'] or "Unknown"
            rows = result['rows']
            filename = result['file'][:30] + "..." if len(result['file']) > 30 else result['file']
            print(f"| {filename} | {latest} | {format_str} | {rows} |")
        else:
            print(f"| {result['file'][:30]}... | ❌ No date | - | {result['rows']} |")

    print()
    print("=" * 70)

    # Find the most recent date across all files
    latest_dates = {}
    for result in all_results:
        if result['latest_date']:
            latest_dates[result['file']] = result['latest_date']

    if latest_dates:
        print("📅 LATEST DATES PER FILE:")
        for file, date in sorted(latest_dates.items()):
            print(f"   {file}: {date}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()