from fastapi import APIRouter, HTTPException
import joblib
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
from ..database.influx_client import get_last_n_readings

router = APIRouter(prefix="/api", tags=["forecast"])

# Load your LSTM model and scaler
MODEL_DIR = "src/api/models/forecast"
model = load_model(f"{MODEL_DIR}/lstm_model.h5")
scaler = joblib.load(f"{MODEL_DIR}/forecast_scaler.pkl")

@router.get("/forecast")
def get_forecast():
    df = get_last_n_readings(96)
    if df.empty or len(df) < 96:
        # Fallback: static prediction if not enough data
        return {
            "latest_actual": 0.0,
            "forecast_5min": 2.36,
            "forecast_15min": 2.41,
            "forecast_30min": 2.48,
            "timestamp": "fallback",
            "source": "static"
        }
    
    # Ensure chronological order
    df = df.sort_values('timestamp')
    target_col = "Global_active_power"
    if target_col not in df.columns:
        raise HTTPException(400, f"Column {target_col} not found")
    
    series = df[target_col].values[-96:]  # take last 96
    # Scale
    X = scaler.transform(series.reshape(-1, 1))
    X_input = X.reshape(1, 96, 1)
    pred = model.predict(X_input, verbose=0)[0]
    # Denormalize
    pred_denorm = scaler.inverse_transform(pred.reshape(-1, 1)).flatten()
    
    return {
        "latest_actual": float(series[-1]),
        "forecast_5min": float(pred_denorm[0]),
        "forecast_15min": float(pred_denorm[1]),
        "forecast_30min": float(pred_denorm[2]),
        "timestamp": df["timestamp"].max().isoformat(),
        "source": "live"
    }