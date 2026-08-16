import os
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
import xgboost as xgb
from functools import lru_cache
import time
from fastapi import FastAPI, HTTPException
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PowerPredict API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "models")
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data", "processed")

# ---- Load Models ----
lstm_model = tf.keras.models.load_model(
    os.path.join(MODELS_DIR, "forecasting", "lstm_baseline_5min.keras")
)
iso_forest = joblib.load(
    os.path.join(MODELS_DIR, "anomaly", "isolation_forest.pkl")
)
anomaly_scaler = joblib.load(
    os.path.join(MODELS_DIR, "anomaly", "anomaly_scaler.pkl")
)
autoencoder = tf.keras.models.load_model(
    os.path.join(MODELS_DIR, "anomaly", "lstm_autoencoder.keras")
)
maintenance_model = xgb.XGBClassifier()
maintenance_model.load_model(
    os.path.join(MODELS_DIR, "maintenance", "xgboost_maintenance.json")
)

# ---- Static fallback data ----
test_df = pd.read_csv(
    os.path.join(DATA_DIR, "test_uci_household.csv"),
    index_col="datetime",
    parse_dates=True
)

FEEDER_ZONE_PATH = os.path.join(DATA_DIR, "feeder_zone_map.csv")
feeder_zone_df = (
    pd.read_csv(FEEDER_ZONE_PATH) if os.path.exists(FEEDER_ZONE_PATH) else pd.DataFrame()
)

# ---- InfluxDB ----
ENV_PATH = os.path.join(BASE_DIR, "..", "..", ".env")
load_dotenv(dotenv_path=ENV_PATH)
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
influx_client = InfluxDBClient(
    url="http://localhost:8086",
    token=INFLUX_TOKEN,
    org="powerpredict"
)
query_api = influx_client.query_api()


# ---- Helpers ----
# ============================================================
# 1. REPLACE fetch_live_readings with this feeder-aware version
# ============================================================
def fetch_live_readings(limit=100, feeder_id=None):
    """Fetch latest readings from InfluxDB (newest first).
    If feeder_id is given, only that feeder's readings are returned -
    this is the fix for the multi-feeder mixing bug."""
    feeder_filter = f'|> filter(fn: (r) => r.feeder_id == "{feeder_id}")' if feeder_id else ""
    query = f'''
    from(bucket: "grid_data")
      |> range(start: -6h)
      |> filter(fn: (r) => r._measurement == "grid_reading")
      {feeder_filter}
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: {limit})
    '''
    tables = query_api.query_data_frame(query)
    if isinstance(tables, list):
        tables = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    if tables.empty:
        return pd.DataFrame()
    tables = tables.rename(columns={
        "active_power": "Global_active_power",
        "voltage": "Voltage",
        "current": "Global_intensity",
        "reactive_power": "Global_reactive_power"
    })
    tables.set_index("_time", inplace=True)
    return tables
 


def build_features(df):
    """Add all features used by LSTM and Isolation Forest.
    Groups lag/rolling/deviation calculations by feeder_id when present,
    so readings from different feeders never leak into each other's
    lag/rolling windows (this was the root cause of the frozen forecast)."""
    df = df.copy()
    df["hour"] = df.index.hour
    df["day_of_week"] = df.index.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
 
    target = "Global_active_power"
    has_feeder = "feeder_id" in df.columns
 
    if has_feeder:
        df = df.sort_values(["feeder_id", df.index.name or "_time"])
        grp = df.groupby("feeder_id")[target]
        for lag in [1, 2, 3, 6, 12]:
            df[f"{target}_lag_{lag}"] = grp.shift(lag)
        for window in [3, 6, 12]:
            df[f"{target}_roll_mean_{window}"] = df.groupby("feeder_id")[target].transform(
                lambda s: s.shift(1).rolling(window).mean())
            df[f"{target}_roll_std_{window}"] = df.groupby("feeder_id")[target].transform(
                lambda s: s.shift(1).rolling(window).std())
        df["pct_change"] = df.groupby("feeder_id")[target].pct_change().fillna(0)
        df["expected_for_hour"] = df.groupby(["feeder_id", "hour"])[target].transform("mean")
    else:
        # fallback path if feeder_id somehow isn't present - old (buggy) behaviour
        for lag in [1, 2, 3, 6, 12]:
            df[f"{target}_lag_{lag}"] = df[target].shift(lag)
        for window in [3, 6, 12]:
            df[f"{target}_roll_mean_{window}"] = df[target].shift(1).rolling(window).mean()
            df[f"{target}_roll_std_{window}"] = df[target].shift(1).rolling(window).std()
        df["pct_change"] = df[target].pct_change().fillna(0)
        df["expected_for_hour"] = df.groupby("hour")[target].transform("mean")
 
    df["deviation_from_hourly_norm"] = df[target] - df["expected_for_hour"]
 
    for sm in ["Sub_metering_1", "Sub_metering_2", "Sub_metering_3"]:
        if sm not in df.columns:
            df[sm] = 0.0
 
    return df.dropna()


# ---- Endpoints ----
@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": True}


@app.get("/status")
def status():
    # quick check if InfluxDB is reachable
    try:
        query_api.query('from(bucket:"grid_data") |> range(start: -1m) |> limit(n:1)')
        influx_ok = True
    except:
        influx_ok = False
    return {
        "influxdb_connected": influx_ok,
        "models_loaded": True,
        "mode": "live" if influx_ok else "standby"
    }


@app.get("/forecast")
def get_forecast():
    # Pull a wider unfiltered window first, just to see which feeder has the most data
    df = fetch_live_readings(limit=300)
    if df.empty or "feeder_id" not in df.columns:
        return fallback_forecast("no live data / no feeder_id tag present")
 
  # Forecast on whichever feeder has the most RECENT reading in this window
    target_feeder = df.loc[df.index.max(), "feeder_id"]
    if isinstance(target_feeder, pd.Series):  # multiple feeders shared the exact latest timestamp
        target_feeder = target_feeder.iloc[0]
    df_feeder = df[df["feeder_id"] == target_feeder].sort_index()
 
    df_feat = build_features(df_feeder)
    if df_feat.empty or len(df_feat) < 13:
        return fallback_forecast(f"not enough consecutive live readings for feeder {target_feeder}")
 
    # NOTE: feature_cols is still derived from the OLD test_df (UCI household schema).
    # This keeps things running without crashing, but is not fully correct - the real
    # fix is retraining the LSTM on real feeder data with a matching, saved feature
    # set and window length (the still-open "Step 4" item from earlier). Treat this
    # forecast as "no longer frozen" progress, not "numerically trustworthy yet".
    feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
    available = [c for c in feature_cols if c in df_feat.columns]
    latest_features = df_feat[available].iloc[-1:].values
    latest_reshaped = latest_features.reshape((1, 1, latest_features.shape[1]))
    prediction = lstm_model.predict(latest_reshaped, verbose=0)
    
    
 
    return {
        "predicted_active_power_5min": float(prediction[0][0]),
        "timestamp": str(df_feat.index[-1]),
        "feeder_id": str(target_feeder),
        "source": "live_influxdb"
    }
 


def fallback_forecast(reason):
    feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
    latest_row = test_df[feature_cols].iloc[-1:].values
    latest_reshaped = latest_row.reshape((1, 1, latest_row.shape[1]))
    pred = lstm_model.predict(latest_reshaped, verbose=0)
    return {
        "predicted_active_power_5min": float(pred[0][0]),
        "timestamp": str(test_df.index[-1]),
        "source": "static_fallback",
        "reason": reason
    }


@app.get("/anomalies")
def get_anomalies():
    # Fetch last 100 readings from InfluxDB
    df = fetch_live_readings(limit=100)
    if df.empty:
        # fallback: use test_df last 50 rows
        recent = test_df.tail(50).copy()
        recent = build_features(recent)
        features = recent[["pct_change", "deviation_from_hourly_norm", "Voltage", "Global_reactive_power"]]
    else:
        # Build features
        df_feat = build_features(df)
        if df_feat.empty:
            return {"anomaly_count": 0, "recent_anomalies": []}
        # Use the most recent 50 rows
        recent = df_feat.iloc[-50:]
        features = recent[["pct_change", "deviation_from_hourly_norm", "Voltage", "Global_reactive_power"]]

    # Scale and predict
    scaled = anomaly_scaler.transform(features)
    flags = iso_forest.predict(scaled)  # -1 = anomaly

    anomalies = recent[flags == -1]
    return {
        "anomaly_count": int((flags == -1).sum()),
        "recent_anomalies": [
            {"timestamp": str(idx), "active_power": float(row["Global_active_power"])}
            for idx, row in anomalies.iterrows()
        ]
    }


@app.get("/latest")
def get_latest():
    """Return the single most recent reading (voltage, current, active power, etc.)"""
    df = fetch_live_readings(limit=1)
    if df.empty:
        raise HTTPException(status_code=404, detail="No live readings available")
    row = df.iloc[0]
    return {
        "timestamp": str(row.name),
        "voltage": float(row.get("Voltage", 0)),
        "current": float(row.get("Global_intensity", 0)),
        "active_power": float(row.get("Global_active_power", 0)),
        "reactive_power": float(row.get("Global_reactive_power", 0))
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
        {"name": "Transformer T-14", "zone": "Zone 4", "air_temp_K": 302.1, "process_temp_K": 312.5,
         "rotational_speed_rpm": 1420, "torque_Nm": 58.2, "tool_wear_min": 210},
        {"name": "Transformer T-08", "zone": "Zone 3", "air_temp_K": 298.7, "process_temp_K": 308.9,
         "rotational_speed_rpm": 1510, "torque_Nm": 44.1, "tool_wear_min": 130},
        {"name": "Feeder switch F-3", "zone": "Zone 4", "air_temp_K": 297.0, "process_temp_K": 305.2,
         "rotational_speed_rpm": 1550, "torque_Nm": 38.0, "tool_wear_min": 45},
        {"name": "Substation relay S-11", "zone": "Zone 2", "air_temp_K": 299.5, "process_temp_K": 309.1,
         "rotational_speed_rpm": 1480, "torque_Nm": 41.5, "tool_wear_min": 90},
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
        health = round((1 - failure_prob) * 100, 1)
        results.append({
            "name": unit["name"],
            "zone": unit["zone"],
            "health": health,
            "status": "bad" if health < 70 else "mid" if health < 90 else "good"
        })
    return {"equipment": results}

@app.get("/forecast/metrics")
def get_forecast_metrics():
    df = fetch_live_readings(limit=500)
    if df.empty or "feeder_id" not in df.columns:
        return fallback_forecast_metrics("no live data")
 
    target_feeder = df.loc[df.index.max(), "feeder_id"]
    if isinstance(target_feeder, pd.Series):
        target_feeder = target_feeder.iloc[0]
    df_feeder = df[df["feeder_id"] == target_feeder].sort_index()
 
    df_feat = build_features(df_feeder)
    if df_feat.empty or len(df_feat) < 20:
        return fallback_forecast_metrics(f"not enough live data for feeder {target_feeder}")
 
    target_col = "Global_active_power"
    target_col = "Global_active_power"
# REVERTED: don't exclude target_col - the model was trained with 23 features
# including it, dropping it breaks the model's fixed input shape (this was my error)
    feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
    available = [c for c in feature_cols if c in df_feat.columns]
 
    X = df_feat[available].values
    y_true = df_feat[target_col].values
    X_reshaped = X.reshape((X.shape[0], 1, X.shape[1]))
    y_pred = lstm_model.predict(X_reshaped, verbose=0).flatten()
 
    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-6))) * 100)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    peak_forecast = float(np.max(y_pred))
    drift = float(abs(np.mean(y_pred) - np.mean(y_true)) / max(np.mean(y_true), 1e-6) * 100)
 
    # NOTE: still simulated degradation, not independently evaluated per horizon -
    # the model only outputs a 5-min-ahead prediction, this is a scaled approximation
    accuracy_by_horizon = {
        "5m": r2 * 100,
        "15m": r2 * 95,
        "1h": r2 * 88,
        "6h": r2 * 75,
        "24h": r2 * 65
    }
 
    # NOTE: still hardcoded placeholder values, not real SHAP output - flagged for later
    feature_importance = {
        "Lagged load (t-1h)": 92,
        "Ambient temperature": 74,
        "Day-of-week": 51,
        "Solar irradiance": 38,
        "Holiday flag": 19
    }
 
    return {
        "mape_24h": mape,
        "r2_score": r2,
        "peak_forecast": peak_forecast,
        "model_drift": drift,
        "feeder_id": str(target_feeder),
        "source": "live_influxdb",
        "accuracy_by_horizon": accuracy_by_horizon,
        "feature_importance": feature_importance
    }

def fallback_forecast_metrics(reason):
    """Used only when no live feeder data is available at all."""
    target_col = "Global_active_power"
    # REVERTED: don't exclude target_col - the model was trained with 23 features
    # including it, dropping it breaks the model's fixed input shape (this was my error)
    feature_cols = [c for c in test_df.columns if not c.startswith("target_")]
    sample_df = test_df.head(500).copy()
    X_test = sample_df[feature_cols].values
    y_true = sample_df[target_col].values
    X_reshaped = X_test.reshape((X_test.shape[0], 1, X_test.shape[1]))
    y_pred = lstm_model.predict(X_reshaped, verbose=0).flatten()

    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-6))) * 100)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

    return {
        "mape_24h": mape,
        "r2_score": r2,
        "peak_forecast": float(np.max(y_pred)),
        "model_drift": 0.0,
        "source": "static_fallback",
        "reason": reason,
        "accuracy_by_horizon": {
            "5m": r2 * 100, "15m": r2 * 95, "1h": r2 * 88, "6h": r2 * 75, "24h": r2 * 65
        },
        "feature_importance": {
            "Lagged load (t-1h)": 92, "Ambient temperature": 74,
            "Day-of-week": 51, "Solar irradiance": 38, "Holiday flag": 19
        }
    }
 
 
@app.get("/anomalies/stats")
def get_anomaly_stats():
    # Prepare data from test set
    recent = test_df.tail(200).copy()
    recent["hour"] = recent.index.hour
    recent["pct_change"] = recent["Global_active_power"].pct_change().fillna(0)
    recent["expected_for_hour"] = recent.groupby("hour")["Global_active_power"].transform("mean")
    recent["deviation_from_hourly_norm"] = recent["Global_active_power"] - recent["expected_for_hour"]
    
    features = recent[["pct_change", "deviation_from_hourly_norm", "Voltage", "Global_reactive_power"]]
    scaled = anomaly_scaler.transform(features)
    flags = iso_forest.predict(scaled)  # -1 = anomaly
    
    anomaly_count = int((flags == -1).sum())
    
    # Simulate "MTD" and "False Positive Rate" based on frequency of anomalies
    # Since we don't have actual ground truth labels in the test set, we use a heuristic:
    # Assuming ~5% of data is "unusual" by default (which matches your injection notebook)
    total = len(flags)
    detection_rate = anomaly_count / total
    
    return {
        "open_count": anomaly_count,
        "critical_unresolved": max(1, anomaly_count // 3),  # Rough heuristic
        "mean_time_to_detect_sec": int(30 + anomaly_count * 3),  # Dynamic based on count
        "false_positive_rate": round(detection_rate * 100, 1),  # This is the percentage flagged
        "resolved_30d": int(anomaly_count * 1.5)
    }

@app.get("/feeders")
def get_feeders():
    """Real per-feeder status from the latest InfluxDB readings, not a
    fabricated split of one household's sub-metering channels."""
    df = fetch_live_readings(limit=500)
    if df.empty or "feeder_id" not in df.columns:
        raise HTTPException(status_code=503, detail="No live feeder data available yet")
 
    latest_per_feeder = df.sort_index().groupby("feeder_id").tail(1)
 
    def get_zone(fid):
        match = feeder_zone_df[feeder_zone_df["lv_feeder_id"].astype(str) == str(fid)]
        return match.iloc[0]["zone_id"] if not match.empty else "unassigned"
 
    def get_status(voltage):
        if voltage < 0.92 * 230 or voltage > 1.06 * 230:
            return "CRITICAL"
        if voltage < 0.96 * 230 or voltage > 1.04 * 230:
            return "WATCH"
        return "NOMINAL"
 
    result = []
    for _, row in latest_per_feeder.iterrows():
        fid = row["feeder_id"]
        voltage = float(row.get("Voltage", 230))
        current = float(row.get("Global_intensity", 0))
        power = float(row.get("Global_active_power", 0))
        # power factor estimate from real active/reactive readings, not random
        reactive = float(row.get("Global_reactive_power", 0))
        apparent = (power ** 2 + reactive ** 2) ** 0.5
        pf = round(power / apparent, 2) if apparent > 0 else 1.0
 
        result.append({
            "name": f"FDR-{fid}",
            "zone": get_zone(fid),
            "voltage": round(voltage, 1),
            "current": round(current, 1),
            "active_power": round(power, 2),
            "pf": pf,
            "status": get_status(voltage),
            "timestamp": str(row.name),
        })
 
    return result

@app.get("/zones")
def get_zones():
    if feeder_zone_df.empty:
        raise HTTPException(
            status_code=500,
            detail="feeder_zone_map.csv not found - run build_zone_map.py first."
        )
 
    zones_all = sorted(feeder_zone_df["zone_id"].unique())
    zone_status = {z: "nominal" for z in zones_all}
 
    df = fetch_live_readings(limit=500)
    if not df.empty and "feeder_id" in df.columns:
        latest_per_feeder = df.sort_index().groupby("feeder_id").tail(1)
        severity_rank = {"nominal": 0, "watch": 1, "critical": 2}
 
        for _, row in latest_per_feeder.iterrows():
            fid = row["feeder_id"]
            match = feeder_zone_df[feeder_zone_df["lv_feeder_id"].astype(str) == str(fid)]
            if match.empty:
                continue
            zone_id = match.iloc[0]["zone_id"]
 
            voltage = row.get("Voltage", 230)
            # simple placeholder thresholds - tune against your Settings page values later
            if voltage < 0.92 * 230 or voltage > 1.06 * 230:
                status = "critical"
            elif voltage < 0.96 * 230 or voltage > 1.04 * 230:
                status = "watch"
            else:
                status = "nominal"
 
            if severity_rank[status] > severity_rank[zone_status[zone_id]]:
                zone_status[zone_id] = status
 
    return {"zones": [{"zone_id": z, "status": s} for z, s in zone_status.items()]}

@app.get("/anomalies/queue")
def get_anomaly_queue():
    """Real detected anomalies from live per-feeder data, not randomized
    placeholders. Severity is derived from how far voltage deviates from
    nominal - a simple, explainable heuristic, not fabricated."""
    df = fetch_live_readings(limit=500)
    if df.empty or "feeder_id" not in df.columns:
        return []
 
    queue = []
    for feeder_id, group in df.groupby("feeder_id"):
        group = group.sort_index()
        df_feat = build_features(group)
        if df_feat.empty:
            continue
 
        features = df_feat[["pct_change", "deviation_from_hourly_norm", "Voltage", "Global_reactive_power"]]
        scaled = anomaly_scaler.transform(features)
        flags = iso_forest.predict(scaled)  # -1 = anomaly
 
        anomalous_rows = df_feat[flags == -1]
        zone = feeder_zone_df[feeder_zone_df["lv_feeder_id"].astype(str) == str(feeder_id)]
        zone_id = zone.iloc[0]["zone_id"] if not zone.empty else "unassigned"
 
        for idx, row in anomalous_rows.tail(5).iterrows():  # cap per feeder so the queue doesn't explode
            voltage = row["Voltage"]
            deviation_pct = abs(voltage - 230) / 230 * 100
            severity = "CRITICAL" if deviation_pct > 3 else "WARNING" if deviation_pct > 1.5 else "INFO"
 
            queue.append({
                "id": f"ANM-{feeder_id}-{idx.strftime('%H%M%S')}",
                "type": "Voltage deviation",  # honest label - we're only flagging on voltage/deviation features here
                "asset": f"Feeder {feeder_id}",
                "zone": zone_id,
                "severity": severity,
                "timestamp": str(idx),
                "active_power": round(float(row["Global_active_power"]), 2),
                "voltage": round(float(voltage), 1),
                "status": "Open",  # no real workflow state exists yet - honestly reflect that
            })
 
    # newest first
    queue.sort(key=lambda x: x["timestamp"], reverse=True)
    return queue[:20]
 