import joblib
import numpy as np
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "models" / "anomaly"

# Load Isolation Forest and scaler
iso_forest = joblib.load(MODEL_DIR / "isolation_forest.pkl")
scaler = joblib.load(MODEL_DIR / "anomaly_scaler.pkl")

# These must match the features used in training
FEATURES = ["pct_change", "deviation_from_hourly_norm", "Voltage", "Global_reactive_power"]

def score_reading(reading_dict):
    """Return anomaly flag (True/False) and score"""
    try:
        row = [reading_dict.get(f, 0.0) for f in FEATURES]
        X = np.array(row).reshape(1, -1)
        X_scaled = scaler.transform(X)
        pred = iso_forest.predict(X_scaled)[0]  # -1 = anomaly, 1 = normal
        is_anomaly = (pred == -1)
        # Score: negative decision_function = more anomalous
        score = iso_forest.decision_function(X_scaled)[0]
        return {"is_anomaly": bool(is_anomaly), "score": float(score)}
    except Exception as e:
        return {"is_anomaly": False, "score": 0.0, "error": str(e)}