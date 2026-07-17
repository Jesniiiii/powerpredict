import json
import os
from dotenv import load_dotenv
from kafka import KafkaConsumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
print(f"Looking for .env at: {env_path}")
print(f"Token loaded: '{INFLUX_TOKEN}'")
print(f"Token length: {len(INFLUX_TOKEN) if INFLUX_TOKEN else 'None'}")

consumer = KafkaConsumer(
    "grid-readings",
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    auto_offset_reset="latest"
)

client = InfluxDBClient(
    url="http://localhost:8086",
    token=INFLUX_TOKEN,
    org="powerpredict"
)
write_api = client.write_api(write_options=SYNCHRONOUS)

print("Consumer started — listening for readings...")

for message in consumer:
    data = message.value
    point = (
        Point("grid_reading")
        .field("active_power", data["active_power"])
        .field("voltage", data["voltage"])
        .field("current", data["current"])
        .field("reactive_power", data["reactive_power"])
    )
    write_api.write(bucket="grid_data", record=point)
    print(f"Written to InfluxDB: {data}")