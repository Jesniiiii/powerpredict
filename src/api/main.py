import os
import joblib
import numpy as np
import tensorflow as tf
import xgboost as xgb
from fastapi import FastAPI

app = FastAPI(title="PowerPredict API")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "models")

lstm_model = tf.keras.models.load_model(os.path.join(MODELS_DIR, "forecasting", "lstm_baseline_5min.keras"))
iso_forest = joblib.load(os.path.join(MODELS_DIR, "anomaly", "isolation_forest.pkl"))
anomaly_scaler = joblib.load(os.path.join(MODELS_DIR, "anomaly", "anomaly_scaler.pkl"))
autoencoder = tf.keras.models.load_model(os.path.join(MODELS_DIR, "anomaly", "lstm_autoencoder.keras"))
maintenance_model = xgb.XGBClassifier()
maintenance_model.load_model(os.path.join(MODELS_DIR, "maintenance", "xgboost_maintenance.json"))

@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": True}

@app.get("/forecast")
def get_forecast():
    return {"forecast": "model loaded, real input wiring next"}

@app.get("/anomalies")
def get_anomalies():
    return {"anomalies": "model loaded, real input wiring next"}

@app.get("/maintenance")
def get_maintenance():
    return {"maintenance": "model loaded, real input wiring next"}