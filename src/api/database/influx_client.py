import os
import pandas as pd
from influxdb_client import InfluxDBClient

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "my-super-secret-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "powerpredict")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "powerpredict")

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()

def get_recent_readings(limit=100):
    """Fetch latest readings (newest first)"""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -1h)
      |> filter(fn: (r) => r._measurement == "power")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: {limit})
    '''
    df = query_api.query_data_frame(query)
    if df is None or df.empty:
        return pd.DataFrame()
    df.rename(columns={'_time': 'timestamp'}, inplace=True)
    return df

def get_last_n_readings(n=96):
    """Fetch last n readings in chronological order (for forecast)"""
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -48h)
      |> filter(fn: (r) => r._measurement == "power")
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
      |> limit(n: {n})
    '''
    df = query_api.query_data_frame(query)
    if df is None or df.empty:
        return pd.DataFrame()
    df.rename(columns={'_time': 'timestamp'}, inplace=True)
    return df