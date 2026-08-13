#!/usr/bin/env python3
"""
Libyana NPM - Daily Scheduler
Full automation pipeline: FTP download → Processing → Health → Email
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
import argparse

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import (
    ConfigManager,
    SFTPDownloader,
    process_site_day,
    process_all_days,
    get_latest_day_folder,
    SITE_SUMMARY_HEADER
)
from backend.csv_history_manager import CSVHistoryManager
from backend.network_kpi_processor import process_network_kpis
from backend.cell_kpi_processor import process_cell_kpis
from backend.traffic_kpi_processor import process_traffic_with_aggregation
from backend.user_kpi_processor import process_user_kpis, aggregate_user_data
from backend.site_detail_processor import generate_site_detail, get_latest_available_day
from backend.health_checker import HealthChecker
from backend.report_generator import ReportGenerator

# Setup logging
LOG_FILE = "scheduler.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DailyScheduler:
    def __init__(self):
        self.config = ConfigManager()
        self.history_mgr = CSVHistoryManager()
        self.health_checker = HealthChecker()
        self.report_gen = ReportGenerator()
        self.today = datetime.now().strftime('%Y-%m-%d')
        self.yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    def run(self, target_date=None, auto_send=False):
        """Run the complete daily pipeline"""
        if target_date is None:
            target_date = self.yesterday

        logger.info("=" * 70)
        logger.info(f"🚀 STARTING DAILY PIPELINE - {target_date}")
        logger.info("=" * 70)
        start_time = time.time()

        try:
            # Step 1: FTP Download
            logger.info("📥 Step 1: Downloading from FTP...")
            if not self._download_ftp(target_date):
                logger.error("❌ FTP download failed, aborting")
                return False

            # Step 2-7: Process all KPIs
            logger.info("📊 Step 2: Processing Site Summary...")
            self._process_site_summary()

            logger.info("📈 Step 3: Processing Network KPIs...")
            self._process_network_kpis()

            logger.info("📊 Step 4: Processing Cell KPIs...")
            self._process_cell_kpis()

            logger.info("📊 Step 5: Processing Traffic KPIs...")
            self._process_traffic_kpis()

            logger.info("👥 Step 6: Processing User KPIs...")
            self._process_user_kpis()

            logger.info("📋 Step 7: Generating Site Detail...")
            self._process_site_detail()

            # Step 8: Export to Excel
            logger.info("💾 Step 8: Exporting to Excel...")
            excel_path = self.history_mgr.export_to_excel()

            # Step 9: Health Check
            logger.info("🏥 Step 9: Running Health Checks...")
            health_data = self._run_health_checks()

            # Step 10: Generate Report
            logger.info("📧 Step 10: Generating Report...")
            report_text, report_excel = self._generate_report(health_data, target_date)

            # Step 11: Email (if auto_send)
            if auto_send:
                logger.info("📧 Step 11: Sending Email Report...")
                self._send_email(report_text, report_excel)

            elapsed = time.time() - start_time
            logger.info("=" * 70)
            logger.info(f"✅ PIPELINE COMPLETED SUCCESSFULLY - {elapsed:.1f} seconds")
            logger.info("=" * 70)
            return True

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _download_ftp(self, target_date):
        """Step 1: Download files from FTP"""
        host = self.config.get('host')
        port = self.config.get('port')
        username = self.config.get('username')
        password = self.config.get('password')
        remote_path = self.config.get('remote_path')
        local_root = self.config.get('local_root')

        downloader = SFTPDownloader(
            host, port, username, password,
            remote_path, local_root,
            log_callback=logger.info
        )

        try:
            if downloader.connect():
                result = downloader.download_and_organize(target_date=target_date)
                downloader.disconnect()
                return result
            return False
        except Exception as e:
            logger.error(f"FTP download failed: {e}")
            return False

    def _process_site_summary(self):
        """Step 2: Process Site Summary"""
        local_root = self.config.get('local_root')
        day_folder = get_latest_day_folder(local_root)

        if day_folder:
            result = process_site_day(day_folder, log_callback=logger.info)
            if result:
                result['day'] = self.yesterday
                self.history_mgr.update_site_row(result)

    def _process_network_kpis(self):
        """Step 3: Process Network KPIs"""
        local_root = self.config.get('local_root')
        day_folder = get_latest_day_folder(local_root)

        if day_folder:
            results = process_network_kpis(day_folder, log_callback=logger.info)
            if results:
                self.history_mgr.update_network_kpis(results)

    def _process_cell_kpis(self):
        """Step 4: Process Cell KPIs"""
        local_root = self.config.get('local_root')
        day_folder = get_latest_day_folder(local_root)

        if day_folder:
            results = process_cell_kpis(day_folder, log_callback=logger.info)
            if results:
                self.history_mgr.update_cell_kpis(results)

    def _process_traffic_kpis(self):
        """Step 5: Process Traffic KPIs"""
        local_root = self.config.get('local_root')
        day_folder = get_latest_day_folder(local_root)

        if day_folder:
            results = process_traffic_with_aggregation(day_folder, log_callback=logger.info)
            if results:
                self.history_mgr.update_traffic_kpis(results)

    def _process_user_kpis(self):
        """Step 6: Process User KPIs"""
        local_root = self.config.get('local_root')
        day_folder = get_latest_day_folder(local_root)

        if day_folder:
            raw_results = process_user_kpis(day_folder, log_callback=logger.info)
            if raw_results:
                self.history_mgr.update_user_kpis(raw_results)
                summary_df = aggregate_user_data(raw_results)
                if summary_df is not None:
                    self.history_mgr.update_user_summary(summary_df)

    def _process_site_detail(self):
        """Step 7: Generate Site Detail"""
        local_root = self.config.get('local_root')
        day_folder = get_latest_day_folder(local_root)

        if day_folder:
            df = generate_site_detail(day_folder, log_callback=logger.info)
            if df is not None and not df.empty:
                self.history_mgr.update_site_detail(df)

    def _run_health_checks(self):
        """Step 9: Run health checks"""
        # Load all data from CSVs
        csv_folder = "output/csv"
        all_data = {}

        sheets = [
            '2G_Cell_CSBH', '2G_NWBH', '2G_NW_Daily',
            '3G_Cell_CSBH', '3G_NWBH', '3G_NW_Daily',
            '4G_Cell_BH', '4G_NWBH', '4G_NW_Daily'
        ]

        for sheet in sheets:
            filepath = os.path.join(csv_folder, f"{sheet}.csv")
            if os.path.exists(filepath):
                try:
                    df = pd.read_csv(filepath)
                    if not df.empty:
                        all_data[sheet] = df
                except:
                    pass

        # Get health summary
        health_data = self.health_checker.get_health_summary(all_data, self.yesterday)

        # Get worst cells
        worst_cells = {}
        for sheet in ['2G_Cell_CSBH', '3G_Cell_CSBH', '4G_Cell_BH']:
            if sheet in all_data:
                tech_map = {
                    '2G_Cell_CSBH': 'GSM',
                    '3G_Cell_CSBH': 'UMTS',
                    '4G_Cell_BH': 'LTE'
                }
                tech = tech_map.get(sheet, 'Unknown')
                df = self.health_checker.find_worst_cells(
                    all_data[sheet], sheet, n_top=10, selected_date=self.yesterday
                )
                if df is not None and not df.empty:
                    worst_cells[tech] = df

        health_data['worst_cells'] = worst_cells
        return health_data

    def _generate_report(self, health_data, target_date):
        """Step 10: Generate report"""
        # Load metrics
        metrics = self._load_metrics(target_date)
        return self.report_gen.generate_report(
            data={},
            metrics=metrics,
            health_summary=health_data,
            worst_cells=health_data.get('worst_cells', {}),
            date_str=target_date
        )

    def _load_metrics(self, target_date):
        """Load metrics for the target date"""
        metrics = {}

        # Load User Summary
        user_file = "output/csv/User_Summary.csv"
        if os.path.exists(user_file):
            try:
                df = pd.read_csv(user_file)
                row = df[df['Date'] == target_date]
                if not row.empty:
                    row = row.iloc[0]
                    metrics['total_ps_users'] = row.get('Total PS Users', 0)
                    metrics['cs_subscribers'] = row.get('2G CS user', 0) + row.get('3G CS user', 0)
                    metrics['volte_users'] = row.get('VoLTE user', 0)
                    metrics['cs_roaming'] = row.get('Roaming CS (Almadar)', 0)
                    metrics['lte_max_users'] = row.get('4G PS user', 0)
            except:
                pass

        # Load Traffic
        traffic_files = {
            '2G': 'Traffic_Network_2G.csv',
            '3G': 'Traffic_Network_3G.csv',
            '4G': 'Traffic_Network_4G.csv'
        }

        total_ps_traffic = 0
        total_cs_traffic = 0
        lte_traffic = 0

        for tech, filename in traffic_files.items():
            filepath = os.path.join("output/csv", filename)
            if os.path.exists(filepath):
                try:
                    df = pd.read_csv(filepath)
                    row = df[df['Date'] == target_date]
                    if not row.empty:
                        row = row.iloc[0]
                        if tech == '2G':
                            total_ps_traffic += row.get('2G PS Traffic (GB)', 0)
                            total_cs_traffic += row.get('2G CS Traffic (Erl)', 0)
                        elif tech == '3G':
                            total_ps_traffic += row.get('3G PS Traffic (GB)', 0)
                            total_cs_traffic += row.get('3G CS Traffic (Erl)', 0)
                        elif tech == '4G':
                            lte_traffic = row.get('4G DL Traffic (GB)', 0)
                            total_ps_traffic += lte_traffic
                except:
                    pass

        metrics['total_ps_traffic'] = total_ps_traffic
        metrics['total_cs_traffic'] = total_cs_traffic
        metrics['lte_traffic'] = lte_traffic

        # Load 4G NWBH
        nw_file = "output/csv/4G_NWBH.csv"
        if os.path.exists(nw_file):
            try:
                df = pd.read_csv(nw_file)
                row = df[df['Date'] == target_date]
                if not row.empty:
                    row = row.iloc[0]
                    metrics['rrc_setup_success'] = row.get('RRC Setup Success Rate(%)', 0)
                    metrics['erab_setup_success'] = row.get('E-RAB Setup Success Rate', 0)
                    metrics['service_drop_rate'] = row.get('Service Drop Rate (All)', 0)
                    metrics['lte_user_throughput'] = row.get('User Downlink Average Throughput (Mbps)', 0)
                    metrics['volte_cssr'] = row.get('VoLTE Setup Success Rate-ZM(%)', 0)
                    metrics['network_availability'] = row.get('Radio Network Availability Rate(%)', 0)
                    metrics['packet_loss'] = row.get('Downlink Packet Loss', 0)
            except:
                pass

        return metrics

    def _send_email(self, report_text, report_excel):
        """Step 11: Send email report"""
        # This would use SMTP - placeholder for now
        logger.info("📧 Email sending not implemented yet")
        logger.info(f"Report text: {report_text}")
        logger.info(f"Report Excel: {report_excel}")


def main():
    parser = argparse.ArgumentParser(description='Libyana NPM Daily Scheduler')
    parser.add_argument('--date', help='Target date (YYYY-MM-DD)', default=None)
    parser.add_argument('--auto-send', action='store_true', help='Auto-send email')
    args = parser.parse_args()

    scheduler = DailyScheduler()

    if args.date:
        target_date = args.date
    else:
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    scheduler.run(target_date=target_date, auto_send=args.auto_send)


if __name__ == "__main__":
    main()