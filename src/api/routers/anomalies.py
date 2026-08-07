from fastapi import APIRouter, HTTPException
import pandas as pd
from ..database.influx_client import get_recent_readings
from ..services.anomaly import score_reading

router = APIRouter(prefix="/api", tags=["anomaly"])

@router.get("/anomalies")
def get_anomalies():
    df = get_recent_readings(limit=50)
    if df.empty:
        return {"anomaly_count": 0, "recent_anomalies": []}
    
    anomalies = []
    for _, row in df.iterrows():
        reading = row.to_dict()
        # Compute required features (simplified)
        reading["pct_change"] = 0.0  # can be improved later
        reading["deviation_from_hourly_norm"] = 0.0
        # Ensure fields exist
        for f in ["Voltage", "Global_reactive_power"]:
            if f not in reading:
                reading[f] = 0.0
        
        result = score_reading(reading)
        if result["is_anomaly"]:
            anomalies.append({
                "timestamp": reading["timestamp"].isoformat(),
                "active_power": reading.get("Global_active_power", 0.0)
            })
    
    return {
        "anomaly_count": len(anomalies),
        "recent_anomalies": anomalies[:10]  # latest 10
    }

@router.get("/latest")
def get_latest():
    df = get_recent_readings(limit=1)
    if df.empty:
        raise HTTPException(404, "No readings found")
    row = df.iloc[0].to_dict()
    return {
        "timestamp": row["timestamp"].isoformat(),
        "voltage": float(row.get("Voltage", 0)),
        "current": float(row.get("Global_intensity", 0)),
        "active_power": float(row.get("Global_active_power", 0)),
        "reactive_power": float(row.get("Global_reactive_power", 0))
    }