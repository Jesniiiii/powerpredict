import os
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
import xgboost as xgb
from fastapi import FastAPI
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

app = FastAPI(title="PowerPredict API")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "models")
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data", "processed")

lstm_model = tf.keras.models.load_model(os.path.join(MODELS_DIR, "forecasting", "lstm_baseline_5min.keras"))
iso_forest = joblib.load(os.path.join(MODELS_DIR, "anomaly", "isolation_forest.pkl"))
anomaly_scaler = joblib.load(os.path.join(MODELS_DIR, "anomaly", "anomaly_scaler.pkl"))
autoencoder = tf.keras.models.load_model(os.path.join(MODELS_DIR, "anomaly", "lstm_autoencoder.keras"))
maintenance_model = xgb.XGBClassifier()
maintenance_model.load_model(os.path.join(MODELS_DIR, "maintenance", "xgboost_maintenance.json"))

test_df = pd.read_csv(os.path.join(DATA_DIR, "test_uci_household.csv"), index_col="datetime", parse_dates=True)

ENV_PATH = os.path.join(BASE_DIR, "..", "..", ".env")
load_dotenv(dotenv_path=ENV_PATH)
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")

influx_client = InfluxDBClient(url="http://localhost:8086", token=INFLUX_TOKEN, org="powerpredict")
query_api = influx_client.query_api()


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": True}


@app.get("/forecast")
def get_forecast():
    query = '''
    from(bucket: "grid_data")
      |> range(start: -2h)
      |> filter(fn: (r) => r._measurement == "grid_reading")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"])
    '''
    tables = query_api.query_data_frame(query)

    if tables.empty or len(tables) < 13:
        # Not enough live history yet — fall back to static test data
        feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
        latest_row = test_df[feature_cols].iloc[-1:].values
        latest_reshaped = latest_row.reshape((1, 1, latest_row.shape[1]))
        prediction = lstm_model.predict(latest_reshaped, verbose=0)
        return {
            "predicted_active_power_5min": float(prediction[0][0]),
            "timestamp": str(test_df.index[-1]),
            "source": "static_fallback",
            "reason": "insufficient live history"
        }

    live_df = tables.rename(columns={
        "active_power": "Global_active_power",
        "voltage": "Voltage",
        "current": "Global_intensity",
        "reactive_power": "Global_reactive_power"
    }).set_index("_time")
    live_df["Sub_metering_1"] = 0.0
    live_df["Sub_metering_2"] = 0.0
    live_df["Sub_metering_3"] = 0.0

    target_col = "Global_active_power"
    for lag in [1, 2, 3, 6, 12]:
        live_df[f"{target_col}_lag_{lag}"] = live_df[target_col].shift(lag)
    for window in [3, 6, 12]:
        live_df[f"{target_col}_roll_mean_{window}"] = live_df[target_col].shift(1).rolling(window).mean()
        live_df[f"{target_col}_roll_std_{window}"] = live_df[target_col].shift(1).rolling(window).std()

    live_df["hour"] = live_df.index.hour
    live_df["day_of_week"] = live_df.index.dayofweek
    live_df["is_weekend"] = (live_df["day_of_week"] >= 5).astype(int)
    live_df["hour_sin"] = np.sin(2 * np.pi * live_df["hour"] / 24)
    live_df["hour_cos"] = np.cos(2 * np.pi * live_df["hour"] / 24)

    live_df = live_df.dropna()

    if live_df.empty:
        feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
        latest_row = test_df[feature_cols].iloc[-1:].values
        latest_reshaped = latest_row.reshape((1, 1, latest_row.shape[1]))
        prediction = lstm_model.predict(latest_reshaped, verbose=0)
        return {
            "predicted_active_power_5min": float(prediction[0][0]),
            "timestamp": str(test_df.index[-1]),
            "source": "static_fallback",
            "reason": "not enough consecutive live readings yet"
        }

    feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
    latest_features = live_df[feature_cols].iloc[-1:].values
    latest_reshaped = latest_features.reshape((1, 1, latest_features.shape[1]))
    prediction = lstm_model.predict(latest_reshaped, verbose=0)

    return {
        "predicted_active_power_5min": float(prediction[0][0]),
        "timestamp": str(live_df.index[-1]),
        "source": "live_influxdb"
    }
    
@app.get("/anomalies")
def get_anomalies():
    recent = test_df.tail(50).copy()
    recent["hour"] = recent.index.hour
    recent["pct_change"] = recent["Global_active_power"].pct_change().fillna(0)
    recent["expected_for_hour"] = recent.groupby("hour")["Global_active_power"].transform("mean")
    recent["deviation_from_hourly_norm"] = recent["Global_active_power"] - recent["expected_for_hour"]

    features = recent[["pct_change", "deviation_from_hourly_norm", "Voltage", "Global_reactive_power"]]
    scaled = anomaly_scaler.transform(features)
    flags = iso_forest.predict(scaled)

    anomalies = recent[flags == -1]
    return {
        "anomaly_count": int((flags == -1).sum()),
        "recent_anomalies": [
            {"timestamp": str(idx), "active_power": float(row["Global_active_power"])}
            for idx, row in anomalies.iterrows()
        ]
    }


@app.get("/maintenance")
def get_maintenance():
    sample_input = pd.DataFrame([{
        "air_temp_K": 298.5,
        "process_temp_K": 308.7,
        "rotational_speed_rpm": 1500,
        "torque_Nm": 42.0,
        "tool_wear_min": 120
    }])
    failure_prob = maintenance_model.predict_proba(sample_input)[0][1]
    return {
        "failure_probability": float(failure_prob),
        "risk_level": "high" if failure_prob > 0.5 else "low"
    }
    
@app.get("/equipment")
def get_equipment():
    sample_units = [
        {"name": "Transformer T-14", "zone": "Zone 4", "air_temp_K": 302.1, "process_temp_K": 312.5, "rotational_speed_rpm": 1420, "torque_Nm": 58.2, "tool_wear_min": 210},
        {"name": "Transformer T-08", "zone": "Zone 3", "air_temp_K": 298.7, "process_temp_K": 308.9, "rotational_speed_rpm": 1510, "torque_Nm": 44.1, "tool_wear_min": 130},
        {"name": "Feeder switch F-3", "zone": "Zone 4", "air_temp_K": 297.0, "process_temp_K": 305.2, "rotational_speed_rpm": 1550, "torque_Nm": 38.0, "tool_wear_min": 45},
        {"name": "Substation relay S-11", "zone": "Zone 2", "air_temp_K": 299.5, "process_temp_K": 309.1, "rotational_speed_rpm": 1480, "torque_Nm": 41.5, "tool_wear_min": 90},
    ]

    results = []
    for unit in sample_units:
        input_df = pd.DataFrame([{
            "air_temp_K": unit["air_temp_K"],
            "process_temp_K": unit["process_temp_K"],
            "rotational_speed_rpm": unit["rotational_speed_rpm"],
            "torque_Nm": unit["torque_Nm"],
            "tool_wear_min": unit["tool_wear_min"]
        }])
        failure_prob = float(maintenance_model.predict_proba(input_df)[0][1])
        health = float(round((1 - failure_prob) * 100, 1))
        results.append({
            "name": unit["name"],
            "zone": unit["zone"],
            "health": health,
            "status": "bad" if health < 70 else "mid" if health < 90 else "good"
        })

    return {"equipment": results}