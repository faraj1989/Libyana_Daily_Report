#!/usr/bin/env python3
"""
Libyana NPM - CSV History Manager
Manages historical data as CSV files instead of Excel.
Combines all CSVs into a single Excel file at the end.
"""

import os
import logging
import pandas as pd
from datetime import datetime
from backend.site_processor import SITE_SUMMARY_HEADER
from backend.site_detail_processor import SITE_DETAIL_HEADER

logger = logging.getLogger(__name__)

# Output folder
OUTPUT_FOLDER = "output"
CSV_FOLDER = os.path.join(OUTPUT_FOLDER, "csv")


class CSVHistoryManager:
    """
    Manages historical data as CSV files.
    Each sheet is stored as a separate CSV file.
    """

    def __init__(self, output_folder=OUTPUT_FOLDER):
        self.output_folder = output_folder
        self.csv_folder = os.path.join(output_folder, "csv")
        self._ensure_folders()

    def _ensure_folders(self):
        """Create output folders if they don't exist."""
        os.makedirs(self.csv_folder, exist_ok=True)
        os.makedirs(self.output_folder, exist_ok=True)

    def _get_csv_path(self, sheet_name):
        """Get the CSV file path for a sheet."""
        # Sanitize sheet name for filename
        safe_name = sheet_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        return os.path.join(self.csv_folder, f"{safe_name}.csv")

    def _read_csv(self, sheet_name):
        """Read a CSV file, return empty DataFrame if not exists."""
        csv_path = self._get_csv_path(sheet_name)
        if os.path.exists(csv_path):
            try:
                return pd.read_csv(csv_path)
            except Exception as e:
                logger.warning(f"Could not read {csv_path}: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def _write_csv(self, sheet_name, df):
        """Write a DataFrame to CSV."""
        if df is None or df.empty:
            logger.warning(f"No data to write to {sheet_name}")
            return

        csv_path = self._get_csv_path(sheet_name)
        try:
            df.to_csv(csv_path, index=False)
            logger.info(f"✅ Wrote {len(df)} rows to {csv_path}")
        except Exception as e:
            logger.error(f"Failed to write {csv_path}: {e}")
            raise

    def _append_with_dup_check(self, sheet_name, df, key_cols):
        """
        Append data with duplicate checking based on key columns.
        Returns (new_count, skipped_count)
        """
        if df is None or df.empty:
            return 0, 0

        try:
            existing_df = self._read_csv(sheet_name)

            if existing_df.empty:
                self._write_csv(sheet_name, df)
                logger.info(f"Created new CSV {sheet_name} with {len(df)} rows")
                return len(df), 0

            # Find available key columns
            available_keys = [col for col in key_cols if col in existing_df.columns and col in df.columns]

            if not available_keys:
                # Use 'Date' or 'day' as fallback key
                for col in ['Date', 'day']:
                    if col in existing_df.columns and col in df.columns:
                        available_keys = [col]
                        break

            if not available_keys:
                # No key columns found, append everything (warning)
                logger.warning(f"{sheet_name}: No key columns found, appending all {len(df)} rows")
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                self._write_csv(sheet_name, combined_df)
                return len(df), 0

            # Create a set of existing keys
            existing_keys = set()
            for _, row in existing_df.iterrows():
                key = tuple(str(row.get(col, '')) for col in available_keys)
                existing_keys.add(key)

            # Filter new rows
            new_rows = []
            dup_count = 0
            for _, row in df.iterrows():
                key = tuple(str(row.get(col, '')) for col in available_keys)
                if key not in existing_keys:
                    new_rows.append(row)
                else:
                    dup_count += 1

            if not new_rows:
                logger.info(f"{sheet_name}: All {len(df)} rows already exist, skipping")
                return 0, len(df)

            # Append new rows
            new_df = pd.DataFrame(new_rows)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            self._write_csv(sheet_name, combined_df)
            logger.info(f"{sheet_name}: Appended {len(new_rows)} new rows (skipped {dup_count} duplicates)")

            return len(new_rows), dup_count

        except Exception as e:
            logger.error(f"Failed to append to {sheet_name}: {e}")
            raise

        
    def update_site_row(self, row_dict):
        """Update or append a row to SiteSummary CSV."""
        if not row_dict:
            return

        day = row_dict.get('day')
        if not day:
            logger.warning("Row has no 'day' field")
            return

        try:
            df = self._read_csv('SiteSummary')
            if not df.empty and day in df['day'].values:
                idx = df[df['day'] == day].index[0]
                for col in SITE_SUMMARY_HEADER:
                    df.at[idx, col] = row_dict.get(col, 0)
                logger.info(f"Updated SiteSummary for day {day}")
            else:
                new_row = pd.DataFrame([row_dict])
                df = pd.concat([df, new_row], ignore_index=True)
                logger.info(f"Appended SiteSummary for day {day}")

            self._write_csv('SiteSummary', df)
        except Exception as e:
            logger.error(f"Failed to update SiteSummary: {e}")
            raise

    def update_site_detail(self, df):
        """Replace the entire SiteDetail CSV."""
        if df is None or df.empty:
            return
        self._write_csv('SiteDetail', df)
        logger.info(f"Updated SiteDetail with {len(df)} rows")

    def update_network_kpis(self, results_dict):
        """Update all network KPI CSVs."""
        if not results_dict:
            return

        total_new = 0
        total_skipped = 0

        for sheet_name, df in results_dict.items():
            if df is not None and not df.empty:
                key_cols = ['Date', 'Whole Network']
                new_count, skipped_count = self._append_with_dup_check(sheet_name, df, key_cols)
                total_new += new_count
                total_skipped += skipped_count

        logger.info(f"Network KPIs: {total_new} new rows, {total_skipped} skipped")
        return total_new, total_skipped

    def update_cell_kpis(self, results_dict):
        """Update all cell KPI CSVs."""
        if not results_dict:
            return

        total_new = 0
        total_skipped = 0

        for sheet_name, df in results_dict.items():
            if df is not None and not df.empty:
                key_cols = ['Date', 'Cell Name']
                new_count, skipped_count = self._append_with_dup_check(sheet_name, df, key_cols)
                total_new += new_count
                total_skipped += skipped_count
                logger.info(f"Cell KPI {sheet_name}: {new_count} new rows, {skipped_count} skipped")

        logger.info(f"Cell KPIs: {total_new} new rows, {total_skipped} skipped")
        return total_new, total_skipped

    def update_traffic_kpis(self, results_dict):
        """Update all traffic KPI CSVs."""
        if not results_dict:
            return

        total_new = 0
        total_skipped = 0

        if 'per_site' in results_dict:
            for sheet_name, df in results_dict['per_site'].items():
                if df is not None and not df.empty:
                    key_cols = ['Date', 'Site']
                    new_count, skipped_count = self._append_with_dup_check(sheet_name, df, key_cols)
                    total_new += new_count
                    total_skipped += skipped_count

        if 'whole_network' in results_dict:
            for sheet_name, df in results_dict['whole_network'].items():
                if df is not None and not df.empty:
                    network_sheet_name = sheet_name.replace('Traffic_', 'Traffic_Network_')
                    key_cols = ['Date']
                    new_count, skipped_count = self._append_with_dup_check(network_sheet_name, df, key_cols)
                    total_new += new_count
                    total_skipped += skipped_count

        logger.info(f"Traffic KPIs: {total_new} new rows, {total_skipped} skipped")
        return total_new, total_skipped

    def update_user_kpis(self, row_dict):
        """Update or append a row to UserKPIs CSV."""
        if not row_dict:
            return

        try:
            df = self._read_csv('UserKPIs')
            day = row_dict.get('Day')

            if not day:
                logger.warning("User KPIs row missing Day")
                return

            if not df.empty and day in df['Day'].values:
                idx = df[df['Day'] == day].index[0]
                for col, value in row_dict.items():
                    if col in df.columns:
                        df.at[idx, col] = value
                logger.info(f"Updated UserKPIs for {day}")
            else:
                new_row = pd.DataFrame([row_dict])
                df = pd.concat([df, new_row], ignore_index=True)
                logger.info(f"Appended UserKPIs for {day}")

            self._write_csv('UserKPIs', df)
        except Exception as e:
            logger.error(f"Failed to update UserKPIs: {e}")
            raise

    def update_packet_loss(self, df):
        """Update Packet Loss CSV."""
        if df is None or df.empty:
            return

        key_cols = ['Date', 'GBSC', 'Adjacent Node Name', 'Adjacent Node Type', 'Adjacent Node ID']
        self._append_with_dup_check('Packet_Loss', df, key_cols)
        logger.info(f"Updated Packet_Loss with {len(df)} rows")

    def update_ept_config(self, df):
        """Replace the entire EPT_Config CSV."""
        if df is None or df.empty:
            return
        self._write_csv('EPT_Config', df)
        logger.info(f"Updated EPT_Config with {len(df)} rows")
    # ---------- User KPI Methods ----------
    def update_user_kpis(self, results_dict):
        """
        Update all user KPI sheets from the results dictionary.
        """
        if not results_dict:
            logger.warning("No user KPI data to update")
            return

        self._ensure_folders()
        total_new = 0
        total_skipped = 0

        for sheet_name, df in results_dict.items():
            if df is not None and not df.empty:
                # Use Date as key column
                key_cols = ['Date']
                new_count, skipped_count = self._append_with_dup_check(sheet_name, df, key_cols)
                total_new += new_count
                total_skipped += skipped_count
                logger.info(f"User KPI {sheet_name}: {new_count} new rows, {skipped_count} skipped")

        logger.info(f"User KPIs updated: {total_new} new rows, {total_skipped} duplicates skipped")
        return total_new, total_skipped

    def update_user_summary(self, df):
        """
        Update the consolidated user summary sheet.
        """
        if df is None or df.empty:
            return

        self._ensure_folders()
        key_cols = ['Date']
        self._append_with_dup_check('User_Summary', df, key_cols)
        logger.info(f"User Summary updated with {len(df)} rows")
    # ---------- Excel Export ----------
    def export_to_excel(self, excel_name="Historical_Network_Data.xlsx"):
        """
        Combine all CSV files into a single Excel workbook.
        """
        excel_path = os.path.join(self.output_folder, excel_name)
        logger.info(f"📁 Exporting all CSVs to Excel: {excel_path}")

        try:
            # Get all CSV files
            csv_files = [f for f in os.listdir(self.csv_folder) if f.endswith('.csv')]

            if not csv_files:
                logger.warning("No CSV files found to export")
                return None

            # Create Excel writer
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                for csv_file in csv_files:
                    sheet_name = csv_file.replace('.csv', '')
                    csv_path = os.path.join(self.csv_folder, csv_file)
                    try:
                        df = pd.read_csv(csv_path)
                        if not df.empty:
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            logger.debug(f"Exported {sheet_name}: {len(df)} rows")
                        else:
                            logger.debug(f"Skipped {sheet_name}: empty")
                    except Exception as e:
                        logger.error(f"Failed to export {csv_file}: {e}")

            logger.info(f"✅ Exported {len(csv_files)} sheets to {excel_path}")
            return excel_path

        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            raise