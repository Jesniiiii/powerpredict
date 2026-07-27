import os
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
import xgboost as xgb
from fastapi import FastAPI

app = FastAPI(title="PowerPredict API")

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


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": True}


@app.get("/forecast")
def get_forecast():
    feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
    latest_row = test_df[feature_cols].iloc[-1:].values
    latest_reshaped = latest_row.reshape((1, 1, latest_row.shape[1]))
    prediction = lstm_model.predict(latest_reshaped, verbose=0)
    return {
        "predicted_active_power_5min": float(prediction[0][0]),
        "timestamp": str(test_df.index[-1])
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