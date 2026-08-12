import pandas as pd
import os

# Check User_Summary
path = "Historical_Network_Data.xlsx"
df = pd.read_excel(path, sheet_name='User_Summary')
print("User_Summary columns:", df.columns.tolist())
print("User_Summary first row:", df.head(1).to_dict())

# Check 4G_NWBH
df4g = pd.read_excel(path, sheet_name='4G_NWBH')
print("\n4G_NWBH columns:", df4g.columns.tolist())
print("4G_NWBH first row:", df4g.head(1).to_dict())

# Check Traffic_Network_4G
df_traffic = pd.read_excel(path, sheet_name='Traffic_Network_4G')
print("\nTraffic_Network_4G columns:", df_traffic.columns.tolist())
print("Traffic_Network_4G first row:", df_traffic.head(1).to_dict())