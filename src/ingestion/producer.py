import json
import time
import os
import pandas as pd
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

script_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(script_dir, "..", "..", "data", "processed", "test_uci_household.csv")

df = pd.read_csv(data_path, index_col="datetime", parse_dates=True)

print(f"Starting simulated stream — {len(df)} readings to send")

for timestamp, row in df.iterrows():
    message = {
        "timestamp": str(timestamp),
        "active_power": float(row["Global_active_power"]),
        "voltage": float(row["Voltage"]),
        "current": float(row["Global_intensity"]),
        "reactive_power": float(row["Global_reactive_power"])
    }
    producer.send("grid-readings", value=message)
    print(f"Sent: {message}")
    time.sleep(2)

print("Stream finished")