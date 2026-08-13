#!/usr/bin/env python3
"""
Libyana NPM - Report Generator
Generates email reports and Excel dashboards with charts
"""

import pandas as pd
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates network performance reports:
    - Email text summary with health scores
    - Excel report with charts
    """

    def __init__(self, output_folder: str = "output/reports"):
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)

    def get_status_icon(self, value: float, threshold: float, operator: str) -> str:
        """Get status icon for a KPI"""
        try:
            value = float(value)
            threshold = float(threshold)

            if operator == ">=":
                passed = value >= threshold
            elif operator == "<=":
                passed = value <= threshold
            elif operator == ">":
                passed = value > threshold
            elif operator == "<":
                passed = value < threshold
            else:
                return "❓"

            return "✅" if passed else "❌"
        except:
            return "❓"

    def get_score_icon(self, score: float) -> Tuple[str, str]:
        """Get icon and color based on score"""
        if score >= 95:
            return "🟢", "Good"
        elif score >= 90:
            return "🟡", "Fair"
        elif score >= 80:
            return "🟠", "Poor"
        else:
            return "🔴", "Critical"

    def get_trend_icon(self, current: float, previous: float) -> str:
        """Get trend icon comparing current vs previous"""
        if pd.isna(current) or pd.isna(previous):
            return "➡️"
        try:
            if current > previous * 1.02:
                return "↑"
            elif current < previous * 0.98:
                return "↓"
            else:
                return "➡️"
        except:
            return "➡️"

    def generate_email_text(self, metrics: Dict, health_summary: Dict,
                            worst_cells: Dict, date_str: str) -> str:
        """
        Generate email report text with health summary and alerts.
        """
        lines = []
        lines.append("=" * 70)
        lines.append(f"📊 LIBYANA NETWORK PERFORMANCE REPORT - {date_str}")
        lines.append("=" * 70)
        lines.append(f"Region: EAST")

        # Overall Health Score
        overall = health_summary.get('overall', {})
        score = overall.get('overall_score', 0)
        icon, status = self.get_score_icon(score)

        lines.append(f"Overall Health Score: {score:.1f}% ({icon} {status})")
        lines.append("")

        # Technology Health
        lines.append("📈 TECHNOLOGY HEALTH:")
        by_tech = health_summary.get('by_technology', {})
        for tech, data in by_tech.items():
            tech_score = data.get('overall_score', 0)
            tech_icon, tech_status = self.get_score_icon(tech_score)
            lines.append(f"  {tech}: {tech_score:.1f}% ({tech_icon} {tech_status})")

        lines.append("")

        # Dimension Scores
        lines.append("📊 DIMENSION SCORES:")
        dim_scores = overall.get('by_dimension', {})
        for dim, data in dim_scores.items():
            dim_score = data.get('score', 0)
            dim_icon, dim_status = self.get_score_icon(dim_score)
            lines.append(f"  {dim}: {dim_score:.1f}% ({dim_icon} {dim_status})")

        lines.append("")

        # Network Summary (KPIs)
        lines.append("📊 NETWORK SUMMARY:")
        lines.append("-" * 50)

        # Extract key metrics from metrics dict
        kpi_list = [
            ("Total PS users (2G+3G+4G)", metrics.get('total_ps_users', 0)),
            ("Total PS traffic (2G+3G+4G)", metrics.get('total_ps_traffic', 0), "GB"),
            ("CS subscribers (2G+3G)", metrics.get('cs_subscribers', 0)),
            ("Total CS traffic (2G+3G)", metrics.get('total_cs_traffic', 0), "Erlangs"),
            ("LTE maximum attached users", metrics.get('lte_max_users', 0)),
            ("Total LTE traffic", metrics.get('lte_traffic', 0), "GB"),
            ("Maximum number of VoLTE users", metrics.get('volte_users', 0)),
            ("Number of max CS roaming users", metrics.get('cs_roaming', 0)),
            ("Average ping packet loss rate", metrics.get('packet_loss', 0)),
            ("RRC Setup Success Rate", metrics.get('rrc_setup_success', 0), "%"),
            ("E-RAB Setup Success Rate", metrics.get('erab_setup_success', 0), "%"),
            ("Average network availability", metrics.get('network_availability', 0), "%"),
            ("Average LTE user DL throughput", metrics.get('lte_user_throughput', 0), "Mbps"),
            ("VoLTE setup success rate", metrics.get('volte_cssr', 0), "%"),
            ("Service drop rate", metrics.get('service_drop_rate', 0), "%")
        ]

        for item in kpi_list:
            if len(item) == 2:
                name, value = item
                unit = ""
            elif len(item) == 3:
                name, value, unit = item
            else:
                continue

            if isinstance(value, (int, float)):
                if value >= 1000:
                    value_str = f"{value:,.2f}" if unit else f"{value:,.0f}"
                else:
                    value_str = f"{value:.4f}" if value < 1 else f"{value:.2f}"
            else:
                value_str = str(value)

            lines.append(f"• {name:40} : {value_str} {unit}".strip())

        lines.append("")

        # Critical Alerts
        alerts = health_summary.get('alerts', [])
        critical_alerts = [a for a in alerts if a.get('severity') == 'Critical']

        lines.append(f"⚠️ CRITICAL ALERTS ({len(critical_alerts)}):")
        if critical_alerts:
            for i, alert in enumerate(critical_alerts[:10], 1):
                lines.append(f"  {i}. {alert['kpi']}: {alert['status']}")
        else:
            lines.append("  ✅ No critical alerts")

        lines.append("")

        # Trend Analysis (last 2 weeks)
        lines.append("📈 TREND ANALYSIS (last 2 weeks):")
        # This would need historical data - we'll add placeholders
        # In full implementation, this would analyze historical CSV data
        lines.append("  • Trend analysis requires historical data from previous reports")
        lines.append("  • Check historical_network_data.xlsx for detailed trends")

        lines.append("")

        # Worst Cells
        lines.append("🔬 TOP 5 WORST CELLS (by Severity Score):")
        lines.append("-" * 70)

        # Collect worst cells from all technologies
        all_worst = []
        for tech, df in worst_cells.items():
            if df is not None and not df.empty:
                all_worst.append((tech, df))

        # Sort and show top 5
        worst_list = []
        for tech, df in all_worst:
            for _, row in df.iterrows():
                worst_list.append({
                    'tech': tech,
                    'cell': row.get('Cell Name', 'Unknown'),
                    'score': row.get('Severity Score', 0),
                    'failing': row.get('Failing KPIs', '')
                })

        worst_list.sort(key=lambda x: x['score'], reverse=True)

        if worst_list:
            lines.append("Rank | Technology | Cell Name | Severity Score | Failing KPIs")
            lines.append("-----|------------|-----------|----------------|---------------")
            for i, item in enumerate(worst_list[:5], 1):
                lines.append(
                    f"  {i}  | {item['tech']:10} | {item['cell'][:20]:20} | {item['score']:14} | {item['failing']}")
        else:
            lines.append("  ✅ No problematic cells detected")

        lines.append("")
        lines.append("📁 Attached: Detailed Excel Report")
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        lines.append("")
        lines.append("Best Regards,")
        lines.append("")
        lines.append("[Team Member's Signature]")

        return "\n".join(lines)

    def generate_excel_report(self, data: Dict, date_str: str, metrics: Dict) -> str:
        """
        Generate Excel report with data and charts.
        """
        filename = f"Network_Report_{date_str}.xlsx"
        filepath = os.path.join(self.output_folder, filename)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Write summary sheet
            summary_data = []
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    if value >= 1000:
                        value_str = f"{value:,.2f}"
                    else:
                        value_str = f"{value:.4f}" if value < 1 else f"{value:.2f}"
                else:
                    value_str = str(value)
                summary_data.append([key, value_str])

            df_summary = pd.DataFrame(summary_data, columns=['Metric', 'Value'])
            df_summary.to_excel(writer, sheet_name='Summary', index=False)

            # Write each data sheet
            for sheet_name, df in data.items():
                if df is not None and not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

        logger.info(f"✅ Excel report saved: {filepath}")
        return filepath

    def generate_report(self, data: Dict, metrics: Dict, health_summary: Dict,
                        worst_cells: Dict, date_str: str) -> Tuple[str, str]:
        """
        Generate complete report (text + Excel).
        Returns: (text_file_path, excel_file_path)
        """
        # Generate email text
        email_text = self.generate_email_text(metrics, health_summary, worst_cells, date_str)
        text_file = os.path.join(self.output_folder, f"Network_Report_{date_str}.txt")
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(email_text)

        # Generate Excel report
        excel_file = self.generate_excel_report(data, date_str, metrics)

        return text_file, excel_file