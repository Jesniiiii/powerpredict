import json
import os
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
from dotenv import load_dotenv
from kafka import KafkaConsumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Load environment
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")

# Paths to models
MODELS_DIR = os.path.join(script_dir, "..", "models")
lstm_model_path = os.path.join(MODELS_DIR, "forecasting", "lstm_baseline_5min.keras")
iso_forest_path = os.path.join(MODELS_DIR, "anomaly", "isolation_forest.pkl")
anomaly_scaler_path = os.path.join(MODELS_DIR, "anomaly", "anomaly_scaler.pkl")

# Load ML Models
print("Loading forecasting and anomaly models into consumer...")
lstm_model = tf.keras.models.load_model(lstm_model_path)
iso_forest = joblib.load(iso_forest_path)
anomaly_scaler = joblib.load(anomaly_scaler_path)
print("Models loaded successfully.")

# Setup Kafka Consumer
consumer = KafkaConsumer(
    "grid-readings",
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    auto_offset_reset="latest"
)

# Setup InfluxDB Client
client = InfluxDBClient(
    url="http://localhost:8086",
    token=INFLUX_TOKEN,
    org="powerpredict"
)
write_api = client.write_api(write_options=SYNCHRONOUS)

# Sliding window buffer to compute online features for each feeder
# We need at least 13 readings to compute rolling/lag features
feeder_buffers = {}

# Keep hourly averages for active power per feeder to compute hourly norm deviation
# We can initialize it dynamically or keep a running mean per hour in memory
hourly_stats = {}  # key: (feeder_id, hour) -> running sum, count

def update_hourly_stats(feeder_id, hour, value):
    key = (feeder_id, hour)
    if key not in hourly_stats:
        hourly_stats[key] = {"sum": 0.0, "count": 0}
    hourly_stats[key]["sum"] += value
    hourly_stats[key]["count"] += 1
    return hourly_stats[key]["sum"] / hourly_stats[key]["count"]

print("Consumer started — listening for readings and running online ML inference...")

for message in consumer:
    data = message.value
    feeder_id = data["feeder_id"]
    zone_id = data["zone_id"]
    active_power = data["active_power"]
    voltage = data["voltage"]
    current = data["current"]
    reactive_power = data["reactive_power"]
    
    timestamp = pd.to_datetime(data["timestamp"])
    hour = timestamp.hour
    day_of_week = timestamp.dayofweek
    is_weekend = int(day_of_week >= 5)
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)

    # Initialize buffer for this feeder if not exists
    if feeder_id not in feeder_buffers:
        feeder_buffers[feeder_id] = []
        
    # Append current reading
    record = {
        "Global_active_power": active_power,
        "Voltage": voltage,
        "Global_intensity": current,
        "Global_reactive_power": reactive_power,
        "hour": hour,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos
    }
    feeder_buffers[feeder_id].append(record)
    
    # Keep only the last 13 readings (needed for 12 lags and rolling windows of size 12)
    if len(feeder_buffers[feeder_id]) > 13:
        feeder_buffers[feeder_id].pop(0)
        
    buffer = feeder_buffers[feeder_id]
    
    # Compute online features if buffer is full
    is_anomaly_predicted = False
    predicted_active_power_5min = 0.0
    
    # 1. Anomaly Detection (requires pct_change and deviation_from_hourly_norm)
    avg_power_for_hour = update_hourly_stats(feeder_id, hour, active_power)
    deviation_from_hourly_norm = active_power - avg_power_for_hour
    
    pct_change = 0.0
    if len(buffer) >= 2:
        prev_active_power = buffer[-2]["Global_active_power"]
        if prev_active_power > 0:
            pct_change = (active_power - prev_active_power) / prev_active_power
            
    # Anomaly features
    anomaly_feats = np.array([[pct_change, deviation_from_hourly_norm, voltage, reactive_power]])
    anomaly_feats_scaled = anomaly_scaler.transform(anomaly_feats)
    anomaly_pred = iso_forest.predict(anomaly_feats_scaled)[0]
    is_anomaly_predicted = bool(anomaly_pred == -1)
    
    # 2. Forecasting
    if len(buffer) == 13:
        # Prepare feature vector for the LSTM model
        # The model expects 24 features:
        # ['Global_active_power', 'Global_reactive_power', 'Voltage', 'Global_intensity',
        #  'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3',
        #  'Global_active_power_lag_1', 'Global_active_power_lag_2', 'Global_active_power_lag_3',
        #  'Global_active_power_lag_6', 'Global_active_power_lag_12',
        #  'Global_active_power_roll_mean_3', 'Global_active_power_roll_std_3',
        #  'Global_active_power_roll_mean_6', 'Global_active_power_roll_std_6',
        #  'Global_active_power_roll_mean_12', 'Global_active_power_roll_std_12',
        #  'hour', 'day_of_week', 'is_weekend', 'hour_sin', 'hour_cos']
        
        # Get historical active powers in order from index 0 to 12 (buffer has 13 items)
        ap_history = [b["Global_active_power"] for b in buffer] # length 13
        
        # Lags relative to current item (index 12 is current)
        lag_1 = ap_history[11]
        lag_2 = ap_history[10]
        lag_3 = ap_history[9]
        lag_6 = ap_history[6]
        lag_12 = ap_history[0]
        
        # Rolling stats (mean/std of historical window ending before current, i.e., index 0..11)
        mean_3 = np.mean(ap_history[9:12])
        std_3 = np.std(ap_history[9:12])
        
        mean_6 = np.mean(ap_history[6:12])
        std_6 = np.std(ap_history[6:12])
        
        mean_12 = np.mean(ap_history[0:12])
        std_12 = np.std(ap_history[0:12])
        
        # Build the 23 features expected (excluding targets)
        feat_vector = [
            active_power,
            reactive_power,
            voltage,
            current,
            0.0, 0.0, 0.0,  # Sub_metering placeholders
            lag_1, lag_2, lag_3, lag_6, lag_12,
            mean_3, float(std_3) if not np.isnan(std_3) else 0.0,
            mean_6, float(std_6) if not np.isnan(std_6) else 0.0,
            mean_12, float(std_12) if not np.isnan(std_12) else 0.0,
            hour,
            day_of_week,
            is_weekend,
            hour_sin,
            hour_cos
        ]
        
        # Reshape for LSTM: [1, 1, 23]
        feat_input = np.array([feat_vector]).reshape((1, 1, len(feat_vector)))
        pred = lstm_model.predict(feat_input, verbose=0)
        predicted_active_power_5min = float(pred[0][0])
    else:
        # Fallback to current load as simple forecast if buffer is not full
        predicted_active_power_5min = float(active_power * 1.02)
        
    # Write to InfluxDB
    point = (
        Point("grid_reading")
        .tag("feeder_id", str(feeder_id))
        .tag("zone_id", str(zone_id))
        .field("active_power", float(active_power))
        .field("voltage", float(voltage))
        .field("current", float(current))
        .field("reactive_power", float(reactive_power))
        .field("is_injected_anomaly", bool(data.get("is_injected_anomaly", False)))
        .field("is_anomaly_predicted", bool(is_anomaly_predicted))
        .field("predicted_active_power_5min", float(predicted_active_power_5min))
    )
    
    anomaly_type = data.get("anomaly_type")
    if anomaly_type and str(anomaly_type) != "nan":
        point = point.tag("anomaly_type", str(anomaly_type))
        
    write_api.write(bucket="grid_data", record=point)
    print(
        f"Processed [{feeder_id} / {zone_id}]: P={active_power:.2f} V={voltage:.1f} | "
        f"AnomalyPred={is_anomaly_predicted} (Injected={data.get('is_injected_anomaly', False)}) | "
        f"Forecast={predicted_active_power_5min:.2f} kW"
    )