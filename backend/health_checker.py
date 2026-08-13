#!/usr/bin/env python3
"""
Libyana NPM - Health Checker
KPI threshold monitoring, health scoring, and worst cells ranking
"""

import pandas as pd
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# Default threshold file path
THRESHOLD_FILE = "config/kpi_thresholds.csv"


class HealthChecker:
    """
    Health checker for network KPIs.
    Loads thresholds, checks KPIs, calculates health scores,
    and identifies worst cells.
    """

    def __init__(self, threshold_file: str = THRESHOLD_FILE):
        self.threshold_file = threshold_file
        self.thresholds = None
        self.load_thresholds()

    def load_thresholds(self):
        """Load KPI thresholds from CSV file"""
        if os.path.exists(self.threshold_file):
            try:
                self.thresholds = pd.read_csv(self.threshold_file)
                logger.info(f"✅ Loaded {len(self.thresholds)} thresholds from {self.threshold_file}")
            except Exception as e:
                logger.error(f"❌ Failed to load thresholds: {e}")
                self.thresholds = None
        else:
            logger.warning(f"⚠️ Threshold file not found: {self.threshold_file}")
            self.thresholds = None

    def normalize_date(self, date_val):
        """Convert date to string format"""
        if date_val is None:
            return None
        if isinstance(date_val, pd.Timestamp):
            return date_val.strftime('%Y-%m-%d')
        try:
            return pd.to_datetime(date_val).strftime('%Y-%m-%d')
        except:
            return str(date_val)

    def check_kpi(self, value: float, threshold: float, operator: str) -> Tuple[bool, str]:
        """
        Check if KPI value meets threshold.
        Returns: (pass, status_message)
        """
        if pd.isna(value) or value is None:
            return False, "No Data"

        try:
            value = float(value)
            threshold = float(threshold)
        except:
            return False, "Invalid Value"

        if operator == ">=":
            passed = value >= threshold
            status = f"{value:.2f} >= {threshold:.2f} {'✅' if passed else '❌'}"
        elif operator == "<=":
            passed = value <= threshold
            status = f"{value:.2f} <= {threshold:.2f} {'✅' if passed else '❌'}"
        elif operator == ">":
            passed = value > threshold
            status = f"{value:.2f} > {threshold:.2f} {'✅' if passed else '❌'}"
        elif operator == "<":
            passed = value < threshold
            status = f"{value:.2f} < {threshold:.2f} {'✅' if passed else '❌'}"
        else:
            passed = False
            status = f"Unknown operator: {operator}"

        return passed, status

    def check_dataframe(self, df: pd.DataFrame, sheet_name: str, date_col: str = 'Date') -> Dict:
        """
        Check all KPIs in a dataframe against thresholds.
        Returns results dictionary.
        """
        if df is None or df.empty or self.thresholds is None:
            return {}

        results = {}

        # Get thresholds for this sheet
        sheet_thresholds = self.thresholds[
            self.thresholds['Source_Sheet'].str.contains(sheet_name, na=False)
        ]

        if sheet_thresholds.empty:
            return {}

        # Check each KPI
        for _, row in sheet_thresholds.iterrows():
            kpi_name = row['KPI_Name']
            column = row['Column_Name']
            threshold = row['Threshold']
            operator = row['Operator']
            weight = row['Weight']
            dimension = row['Dimension']
            severity = row['Severity']
            aggregation = row['Aggregation']

            if column not in df.columns:
                continue

            # Get values (whole network or cell-level)
            if aggregation == 'Whole Network' or 'Whole Network' in df.columns:
                # Get whole network row
                if 'Whole Network' in df.columns:
                    wb_data = df[df['Whole Network'] == 'Whole Network']
                    if not wb_data.empty and column in wb_data.columns:
                        values = wb_data[column]
                    else:
                        values = df[column]
                else:
                    values = df[column]
            else:
                # Cell-level - average across cells
                values = df[column]
                # For worst cells, we store individual values later

            if values.empty:
                continue

            # Calculate average for cell-level
            if aggregation != 'Whole Network' and 'Cell' in aggregation:
                avg_value = values.mean()
            else:
                # For whole network, use the single value
                avg_value = values.iloc[0] if not values.empty else None

            # Check against threshold
            passed, status = self.check_kpi(avg_value, threshold, operator)

            results[kpi_name] = {
                'value': avg_value,
                'threshold': threshold,
                'operator': operator,
                'passed': passed,
                'status': status,
                'weight': weight,
                'dimension': dimension,
                'severity': severity,
                'aggregation': aggregation,
                'column': column
            }

        return results

    def calculate_health_score(self, results: Dict, date_str: str = None) -> Dict:
        """
        Calculate weighted health score from KPI results.
        Returns: {
            'overall_score': float,
            'by_technology': {...},
            'by_dimension': {...},
            'total_kpis': int,
            'passed_kpis': int,
            'failed_kpis': int,
            'alerts': [...]
        }
        """
        if not results:
            return {
                'overall_score': 0,
                'by_technology': {},
                'by_dimension': {},
                'total_kpis': 0,
                'passed_kpis': 0,
                'failed_kpis': 0,
                'alerts': []
            }

        # Group by technology (derived from KPI name)
        tech_map = {
            'GSM': ['GSM', 'TBF', 'SDCCH', 'TCH'],
            'UMTS': ['UMTS', 'RRC', 'RAB', 'AMR', 'HSDPA'],
            'LTE': ['LTE', 'E-RAB', 'CSFB', 'PRB']
        }

        tech_scores = {}
        dimension_scores = {}
        total_weight = 0
        weighted_sum = 0
        passed_count = 0
        failed_count = 0
        alerts = []

        for kpi_name, data in results.items():
            if data['value'] is None or pd.isna(data['value']):
                continue

            weight = data['weight']
            passed = data['passed']
            dimension = data['dimension']
            severity = data['severity']

            # Update overall
            total_weight += weight
            weighted_sum += (weight * (1 if passed else 0))

            if passed:
                passed_count += 1
            else:
                failed_count += 1
                alerts.append({
                    'kpi': kpi_name,
                    'value': data['value'],
                    'threshold': data['threshold'],
                    'severity': severity,
                    'status': data['status']
                })

            # Update dimension scores
            if dimension not in dimension_scores:
                dimension_scores[dimension] = {'weighted': 0, 'total_weight': 0}
            dimension_scores[dimension]['weighted'] += (weight * (1 if passed else 0))
            dimension_scores[dimension]['total_weight'] += weight

            # Update technology scores
            tech = 'Other'
            for t, keywords in tech_map.items():
                if any(kw in kpi_name for kw in keywords):
                    tech = t
                    break

            if tech not in tech_scores:
                tech_scores[tech] = {'weighted': 0, 'total_weight': 0}
            tech_scores[tech]['weighted'] += (weight * (1 if passed else 0))
            tech_scores[tech]['total_weight'] += weight

        # Calculate percentages
        overall_score = (weighted_sum / total_weight * 100) if total_weight > 0 else 0

        for dim in dimension_scores:
            dim_data = dimension_scores[dim]
            dim_data['score'] = (dim_data['weighted'] / dim_data['total_weight'] * 100) if dim_data[
                                                                                               'total_weight'] > 0 else 0

        for tech in tech_scores:
            tech_data = tech_scores[tech]
            tech_data['score'] = (tech_data['weighted'] / tech_data['total_weight'] * 100) if tech_data[
                                                                                                  'total_weight'] > 0 else 0

        return {
            'overall_score': overall_score,
            'by_technology': tech_scores,
            'by_dimension': dimension_scores,
            'total_kpis': passed_count + failed_count,
            'passed_kpis': passed_count,
            'failed_kpis': failed_count,
            'alerts': sorted(alerts, key=lambda x: 0 if x['severity'] == 'Critical' else 1)
        }

    def find_worst_cells(self, df, sheet_name: str, date_col: str = 'Date',
                         n_top: int = 5, selected_date: str = None) -> pd.DataFrame:
        """
        Find worst cells based on severity score.

        Severity Score = (Sum of (Fail weight * 10)) + (Number of violations * 5)

        Returns DataFrame with columns:
        Rank, Technology, Cell Name, Severity Score,
        Accessibility, Retainability, Mobility, Congestion, Failing KPIs
        """
        if df is None or df.empty or self.thresholds is None:
            return pd.DataFrame()

        # Filter by date if provided
        if selected_date and date_col in df.columns:
            target_date = self.normalize_date(selected_date)
            df['_norm_date'] = df[date_col].apply(self.normalize_date)
            df = df[df['_norm_date'] == target_date]

        if df.empty:
            return pd.DataFrame()

        # Get thresholds for this sheet
        sheet_thresholds = self.thresholds[
            self.thresholds['Source_Sheet'].str.contains(sheet_name, na=False)
        ]

        if sheet_thresholds.empty:
            return pd.DataFrame()

        # Identify cell column name
        cell_col = None
        if 'Cell Name' in df.columns:
            cell_col = 'Cell Name'
        elif 'Site Name' in df.columns:
            cell_col = 'Site Name'
        elif 'NodeB Name' in df.columns:
            cell_col = 'NodeB Name'
        elif 'eNodeB Name' in df.columns:
            cell_col = 'eNodeB Name'

        if cell_col is None:
            return pd.DataFrame()

        # Group by cell
        cells = df[cell_col].unique()
        results = []

        for cell in cells:
            cell_data = df[df[cell_col] == cell]
            severity_score = 0
            violations = []
            kpi_values = {}

            # Check each KPI for this cell
            for _, row in sheet_thresholds.iterrows():
                kpi_name = row['KPI_Name']
                column = row['Column_Name']
                threshold = row['Threshold']
                operator = row['Operator']
                weight = row['Weight']
                dimension = row['Dimension']
                tech = row['Technology']

                if column not in cell_data.columns:
                    continue

                # Get value (average across rows for this cell)
                value = cell_data[column].mean()

                if pd.isna(value):
                    continue

                # Store value for display
                kpi_values[kpi_name] = value
                kpi_values[f'{kpi_name}_pass'] = True

                # Check threshold
                passed, status = self.check_kpi(value, threshold, operator)

                if not passed:
                    severity_score += (weight * 10) + 5
                    violations.append({
                        'kpi': kpi_name,
                        'value': value,
                        'threshold': threshold,
                        'weight': weight,
                        'dimension': dimension,
                        'status': status
                    })
                    kpi_values[f'{kpi_name}_pass'] = False

            if violations:
                # Determine technology
                tech = row.get('Technology', 'Unknown') if 'row' in locals() else 'Unknown'

                # Get dimension-specific values (Golden 5)
                acc_val = kpi_values.get('Call Setup Success Rate(%)' if tech == 'GSM' else
                                         'RRC Setup Success Ratio_EFD' if tech == 'UMTS' else
                                         'RRC Setup Success Rate(%)', 'N/A')
                ret_val = kpi_values.get('TCH Drop Rate(%)' if tech == 'GSM' else
                                         'CS Call Drop Rate(%)' if tech == 'UMTS' else
                                         'Service Drop Rate (All)', 'N/A')
                mob_val = kpi_values.get('Handover Success Rate(%)' if tech == 'GSM' else
                                         'Soft Handover Success Rate(%)' if tech == 'UMTS' else
                                         'Intra-HO execute Success Rate', 'N/A')
                con_val = kpi_values.get('TCH Congestion Rate(%)' if tech == 'GSM' else
                                         'PS RAB Setup Success Ratio_EFD' if tech == 'UMTS' else
                                         'DL PRB Utilizing Rate(%)', 'N/A')

                # Build failing KPIs string
                fail_str = ', '.join([f"{v['kpi']} ({v['value']:.2f} | Fail)" for v in violations[:3]])
                if len(violations) > 3:
                    fail_str += f" +{len(violations) - 3} more"

                results.append({
                    'Technology': tech,
                    'Cell Name': cell,
                    'Severity Score': severity_score,
                    'Accessibility': acc_val,
                    'Retainability': ret_val,
                    'Mobility': mob_val,
                    'Congestion': con_val,
                    'Failing KPIs': fail_str,
                    'Violations': violations
                })

        # Sort by severity score (highest first)
        results.sort(key=lambda x: x['Severity Score'], reverse=True)

        # Return top N
        df_results = pd.DataFrame(results[:n_top])
        if not df_results.empty:
            df_results.insert(0, 'Rank', range(1, len(df_results) + 1))

        return df_results

    def get_health_summary(self, all_data: Dict, selected_date: str = None) -> Dict:
        """
        Get complete health summary for all technologies.
        """
        summary = {
            'date': selected_date or datetime.now().strftime('%Y-%m-%d'),
            'by_technology': {},
            'overall': {},
            'worst_cells': {},
            'alerts': []
        }

        # Check each technology
        tech_mapping = {
            '2G_NWBH': 'GSM',
            '2G_NW_Daily': 'GSM',
            '2G_Cell_CSBH': 'GSM',
            '3G_NWBH': 'UMTS',
            '3G_NW_Daily': 'UMTS',
            '3G_Cell_CSBH': 'UMTS',
            '4G_NWBH': 'LTE',
            '4G_NW_Daily': 'LTE',
            '4G_Cell_BH': 'LTE'
        }

        all_results = {}

        for sheet_name, df in all_data.items():
            if sheet_name not in tech_mapping:
                continue

            tech = tech_mapping[sheet_name]
            results = self.check_dataframe(df, sheet_name)

            if results:
                if tech not in all_results:
                    all_results[tech] = {}
                all_results[tech].update(results)

        # Calculate health for each technology
        overall_alerts = []
        for tech, results in all_results.items():
            tech_health = self.calculate_health_score(results, selected_date)
            summary['by_technology'][tech] = tech_health
            overall_alerts.extend(tech_health.get('alerts', []))

        # Overall health (combine all technologies)
        combined_results = {}
        for tech, results in all_results.items():
            combined_results.update(results)

        summary['overall'] = self.calculate_health_score(combined_results, selected_date)
        summary['alerts'] = overall_alerts

        return summary