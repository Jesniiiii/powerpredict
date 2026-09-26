import json
import os
import math
from collections import deque, defaultdict
from datetime import datetime

import numpy as np
import joblib
import tensorflow as tf
from dotenv import load_dotenv
from kafka import KafkaConsumer
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ---- Paths / env ----
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

MODELS_DIR = os.path.join(script_dir, "..", "models", "anomaly")

INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
print(f"Looking for .env at: {env_path}")
print(f"Token loaded: {'yes' if INFLUX_TOKEN else 'NO — check .env path/contents'}")

# ---- Load autoencoder anomaly model ----
print("Loading autoencoder anomaly model...")
autoencoder = tf.keras.models.load_model(os.path.join(MODELS_DIR, "lstm_autoencoder.keras"))
autoencoder_scaler = joblib.load(os.path.join(MODELS_DIR, "autoencoder_scaler.pkl"))
with open(os.path.join(MODELS_DIR, "autoencoder_config.json")) as f:
    autoencoder_config = json.load(f)

FEATURE_COLS = autoencoder_config["feature_cols"]
WINDOW = autoencoder_config["window"]
THRESHOLD = autoencoder_config["threshold"]
N_FEATURES = len(FEATURE_COLS)
print(f"Autoencoder ready: window={WINDOW}, features={FEATURE_COLS}, threshold={THRESHOLD:.5f}")


# ---- Per-feeder online state ----
class FeederState:
    """Causal (online) versions of the offline groupby().transform() features.
    Welford's algorithm gives running mean/variance of Global_active_power
    without storing full history. z-scores use stats from BEFORE the current
    point is folded in, so a point never contributes to its own baseline."""

    def __init__(self):
        self.last_power = None
        self.power_count = 0
        self.power_mean = 0.0
        self.power_m2 = 0.0
        self.hour_count = defaultdict(int)
        self.hour_mean = defaultdict(float)
        self.window = deque(maxlen=WINDOW)

    def power_std(self):
        if self.power_count < 2:
            return None
        return math.sqrt(self.power_m2 / (self.power_count - 1))

    def update_power_stats(self, value):
        self.power_count += 1
        delta = value - self.power_mean
        self.power_mean += delta / self.power_count
        delta2 = value - self.power_mean
        self.power_m2 += delta * delta2

    def update_hour_stats(self, hour, value):
        self.hour_count[hour] += 1
        n = self.hour_count[hour]
        self.hour_mean[hour] += (value - self.hour_mean[hour]) / n


feeder_states = defaultdict(FeederState)


def compute_live_features(feeder_id, hour, active_power, voltage, reactive_power):
    state = feeder_states[feeder_id]

    if state.last_power is not None and state.last_power != 0:
        pct_change = (active_power - state.last_power) / state.last_power
    else:
        pct_change = 0.0

    if state.hour_count[hour] > 0:
        expected_for_hour = state.hour_mean[hour]
    else:
        expected_for_hour = active_power  # first time seen this hour -> zero deviation
    deviation_from_hourly_norm = active_power - expected_for_hour

    feeder_std = state.power_std()
    if feeder_std:
        deviation_zscore = deviation_from_hourly_norm / feeder_std
        power_zscore = (active_power - state.power_mean) / feeder_std
    else:
        deviation_zscore = 0.0
        power_zscore = 0.0

    # update AFTER computing this point's features (causal ordering)
    state.update_power_stats(active_power)
    state.update_hour_stats(hour, active_power)
    state.last_power = active_power

    values = {
        "pct_change": pct_change,
        "deviation_zscore": deviation_zscore,
        "power_zscore": power_zscore,
        "Voltage": voltage,
        "Global_reactive_power": reactive_power,
    }
    return [values[c] for c in FEATURE_COLS]


def score_window(feeder_id, feature_row):
    """Returns (is_anomaly, reconstruction_error), or (None, None) if this
    feeder doesn't have WINDOW readings yet (still warming up)."""
    state = feeder_states[feeder_id]
    state.window.append(feature_row)

    if len(state.window) < WINDOW:
        return None, None

    X = np.array(state.window, dtype=float)          # (WINDOW, N_FEATURES)
    X_scaled = autoencoder_scaler.transform(X)         # scaler fit per-row, matches training
    X_input = X_scaled.reshape(1, WINDOW, N_FEATURES)
    recon = autoencoder.predict(X_input, verbose=0)
    error = float(np.mean(np.square(X_scaled - recon[0])))
    return bool(error > THRESHOLD), error


# ---- Kafka + InfluxDB ----
consumer = KafkaConsumer(
    "grid-readings",
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    auto_offset_reset="latest"
)

client = InfluxDBClient(url="http://localhost:8086", token=INFLUX_TOKEN, org="powerpredict")
write_api = client.write_api(write_options=SYNCHRONOUS)

print("Consumer started — listening for readings...")

for message in consumer:
    data = message.value
    feeder_id = data["feeder_id"]
    zone_id = data["zone_id"]
    active_power = float(data["active_power"])
    voltage = float(data["voltage"])
    current = float(data["current"])
    reactive_power = float(data["reactive_power"])

    ts = datetime.fromisoformat(data["timestamp"])
    hour = ts.hour

    feature_row = compute_live_features(feeder_id, hour, active_power, voltage, reactive_power)
    is_anomaly_live, recon_error = score_window(feeder_id, feature_row)

    point = (
        Point("grid_reading")
        .tag("feeder_id", feeder_id)
        .tag("zone_id", zone_id)
        .field("active_power", active_power)
        .field("voltage", voltage)
        .field("current", current)
        .field("reactive_power", reactive_power)
        .field("is_injected_anomaly", data.get("is_injected_anomaly", False))
    )
    if data.get("anomaly_type"):
        point = point.tag("anomaly_type", data["anomaly_type"])
    if recon_error is not None:
        point = point.field("live_reconstruction_error", recon_error)
        point = point.field("live_is_anomaly", is_anomaly_live)

    write_api.write(bucket="grid_data", record=point)

    if recon_error is None:
        status = "warming up"
    elif is_anomaly_live:
        status = f"ANOMALY (err={recon_error:.4f})"
    else:
        status = f"normal (err={recon_error:.4f})"

    print(
        f"Written [{feeder_id} / {zone_id}]: "
        f"P={active_power:.2f} V={voltage:.1f} live_anomaly={status}"
    )