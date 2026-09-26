import os
import joblib
import json
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
from src.api.routers.auth import router as auth_router
from src.api import alerts
from src.models.maintenance_diagnosis import diagnose_row, URGENCY_BY_CRITICALITY

app = FastAPI(title="PowerPredict API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "models")
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data", "processed")

SETTINGS_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "app_settings.json")
FAULTS_PATH = os.path.join(BASE_DIR, "..", "..", "data", "raw", "faults", "ukpn-live-faults.csv")

DEFAULT_SETTINGS = {
    "min_voltage_threshold": 210,
    "voltage_warning_pct": 1.5,
    "voltage_critical_pct": 3.0,
}


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            saved = json.load(f)
        return {**DEFAULT_SETTINGS, **saved}
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)

# ---- Load Models ----
lstm_model = tf.keras.models.load_model(
    os.path.join(MODELS_DIR, "forecasting", "lstm_baseline_30min.keras")
)
forecast_scaler = joblib.load(
    os.path.join(MODELS_DIR, "forecasting", "forecast_scaler.pkl")
)
with open(os.path.join(MODELS_DIR, "forecasting", "forecast_config.json")) as f:
    forecast_config = json.load(f)
FORECAST_FEATURE_COLS = forecast_config["feature_cols"]

# ---- Anomaly model: autoencoder (replaces Isolation Forest) ----
autoencoder = tf.keras.models.load_model(
    os.path.join(MODELS_DIR, "anomaly", "lstm_autoencoder.keras")
)
autoencoder_scaler = joblib.load(
    os.path.join(MODELS_DIR, "anomaly", "autoencoder_scaler.pkl")
)
with open(os.path.join(MODELS_DIR, "anomaly", "autoencoder_config.json")) as f:
    autoencoder_config = json.load(f)
ANOMALY_FEATURE_COLS = autoencoder_config["feature_cols"]
ANOMALY_WINDOW = autoencoder_config["window"]
ANOMALY_THRESHOLD = autoencoder_config["threshold"]

maintenance_model = joblib.load(
    os.path.join(MODELS_DIR, "maintenance", "rf_maintenance.pkl")
)
with open(os.path.join(MODELS_DIR, "maintenance", "maintenance_config.json")) as f:
    maintenance_config = json.load(f)
MAINTENANCE_FEATURE_COLS = maintenance_config["feature_cols"]
MAINTENANCE_REF_STATS = maintenance_config.get("diagnosis_reference_stats", {})
maintenance_sample = pd.read_csv(
    os.path.join(MODELS_DIR, "maintenance", "maintenance_sample.csv")
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
def fetch_live_readings(limit=100, feeder_id=None):
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
        feeder_std = df.groupby("feeder_id")[target].transform("std")
        feeder_mean = df.groupby("feeder_id")[target].transform("mean")
    else:
        for lag in [1, 2, 3, 6, 12]:
            df[f"{target}_lag_{lag}"] = df[target].shift(lag)
        for window in [3, 6, 12]:
            df[f"{target}_roll_mean_{window}"] = df[target].shift(1).rolling(window).mean()
            df[f"{target}_roll_std_{window}"] = df[target].shift(1).rolling(window).std()
        df["pct_change"] = df[target].pct_change().fillna(0)
        df["expected_for_hour"] = df.groupby("hour")[target].transform("mean")
        feeder_std = pd.Series(df[target].std(), index=df.index)
        feeder_mean = pd.Series(df[target].mean(), index=df.index)

    df["deviation_from_hourly_norm"] = df[target] - df["expected_for_hour"]
    df["deviation_zscore"] = (df["deviation_from_hourly_norm"] / feeder_std.replace(0, np.nan)).fillna(0)
    df["power_zscore"] = ((df[target] - feeder_mean) / feeder_std.replace(0, np.nan)).fillna(0)

    for sm in ["Sub_metering_1", "Sub_metering_2", "Sub_metering_3"]:
        if sm not in df.columns:
            df[sm] = 0.0

    return df.dropna()


def build_sliding_windows(df, feature_cols, window):
    feats = df[feature_cols].values
    n = len(df)
    if n < window:
        return np.empty((0, window, len(feature_cols))), []
    X, end_idx = [], []
    for i in range(n - window + 1):
        X.append(feats[i:i + window])
        end_idx.append(df.index[i + window - 1])
    return np.array(X), end_idx


def score_autoencoder_windows(X):
    if len(X) == 0:
        return np.array([])
    n, w, f = X.shape
    X_scaled = autoencoder_scaler.transform(X.reshape(-1, f)).reshape(n, w, f)
    recon = autoencoder.predict(X_scaled, verbose=0)
    return np.mean(np.square(X_scaled - recon), axis=(1, 2))


def detect_anomalies(df_feat):
    if df_feat.empty:
        return df_feat.assign(reconstruction_error=[])

    flagged_rows = []
    if "feeder_id" in df_feat.columns:
        groups = [(fid, g.sort_index()) for fid, g in df_feat.groupby("feeder_id")]
    else:
        groups = [(None, df_feat.sort_index())]

    for _, group in groups:
        X, end_idx = build_sliding_windows(group, ANOMALY_FEATURE_COLS, ANOMALY_WINDOW)
        if len(X) == 0:
            continue
        errors = score_autoencoder_windows(X)
        for idx, err, is_flagged in zip(end_idx, errors, errors > ANOMALY_THRESHOLD):
            if is_flagged:
                row = group.loc[[idx]].copy()
                row["reconstruction_error"] = float(err)
                flagged_rows.append(row)

    if not flagged_rows:
        empty = df_feat.iloc[0:0].copy()
        empty["reconstruction_error"] = pd.Series(dtype=float)
        return empty
    return pd.concat(flagged_rows)


def _zone_lookup(fid):
    """Returns (zone_id, criticality_tier, facility_type) for a feeder id."""
    match = feeder_zone_df[feeder_zone_df["lv_feeder_id"].astype(str) == str(fid)]
    if match.empty:
        return "unassigned", "Low", "Unassigned"
    row = match.iloc[0]
    return (
        row.get("zone_id", "unassigned"),
        row.get("criticality_tier", "Low"),
        row.get("facility_type", "Unassigned"),
    )


def _diagnose_maintenance_row(row):
    """Shared by /maintenance and /equipment: real fault_type/recommendation/urgency
    off diagnose_row(), or a plain non-risk fallback if the row wasn't flagged high-risk."""
    failure_prob_col_present = "high_risk" in row.index
    zone_id = row.get("zone_id", "unassigned")
    criticality_tier = row.get("criticality_tier", "Low")
    is_high_risk = bool(row.get("high_risk", 0)) if failure_prob_col_present else None

    if is_high_risk:
        fault_type, recommendation = diagnose_row(row, MAINTENANCE_REF_STATS)
        urgency = URGENCY_BY_CRITICALITY.get(criticality_tier, "Schedule routine inspection")
    else:
        fault_type = "Normal - no risk flagged"
        recommendation = "No action needed; continue routine monitoring."
        urgency = "Routine"

    return fault_type, recommendation, urgency, zone_id, criticality_tier


# ---- Endpoints ----
@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": True}


@app.get("/status")
def status():
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
    df = fetch_live_readings(limit=300)
    if df.empty or "feeder_id" not in df.columns:
        return fallback_forecast("no live data / no feeder_id tag present")

    target_feeder = df.loc[df.index.max(), "feeder_id"]
    if isinstance(target_feeder, pd.Series):
        target_feeder = target_feeder.iloc[0]
    df_feeder = df[df["feeder_id"] == target_feeder].sort_index()

    df_feat = build_features(df_feeder)
    if df_feat.empty or len(df_feat) < 13:
        return fallback_forecast(f"not enough consecutive live readings for feeder {target_feeder}")

    available = [c for c in FORECAST_FEATURE_COLS if c in df_feat.columns]
    if len(available) != len(FORECAST_FEATURE_COLS):
        missing = set(FORECAST_FEATURE_COLS) - set(available)
        return fallback_forecast(f"live features missing columns the model needs: {missing}")

    latest_features = df_feat[FORECAST_FEATURE_COLS].iloc[-1:].values
    latest_scaled = forecast_scaler.transform(latest_features)
    latest_reshaped = latest_scaled.reshape((1, 1, latest_scaled.shape[1]))
    prediction = lstm_model.predict(latest_reshaped, verbose=0)

    return {
        "predicted_active_power_next": float(prediction[0][0]),
        "horizon_minutes": 30,
        "timestamp": str(df_feat.index[-1]),
        "feeder_id": str(target_feeder),
        "source": "live_influxdb"
    }


def fallback_forecast(reason):
    feature_cols = FORECAST_FEATURE_COLS
    latest_row = test_df[feature_cols].iloc[-1:].values
    latest_scaled = forecast_scaler.transform(latest_row)
    latest_reshaped = latest_scaled.reshape((1, 1, latest_scaled.shape[1]))
    pred = lstm_model.predict(latest_reshaped, verbose=0)
    return {
        "predicted_active_power_next": float(pred[0][0]),
        "horizon_minutes": 30,
        "timestamp": str(test_df.index[-1]),
        "source": "static_fallback",
        "reason": reason
    }


@app.get("/anomalies")
def get_anomalies():
    df = fetch_live_readings(limit=100)
    if df.empty:
        recent = test_df.tail(50 + ANOMALY_WINDOW - 1).copy()
        recent_feat = build_features(recent)
    else:
        recent_feat = build_features(df)
        if recent_feat.empty:
            return {"anomaly_count": 0, "recent_anomalies": []}

    anomalies = detect_anomalies(recent_feat)
    return {
        "anomaly_count": int(len(anomalies)),
        "recent_anomalies": [
            {
                "timestamp": str(idx),
                "active_power": float(row["Global_active_power"]),
                "reconstruction_error": float(row["reconstruction_error"]),
            }
            for idx, row in anomalies.iterrows()
        ]
    }


@app.get("/latest")
def get_latest():
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
    row_idx = int(pd.Timestamp.now().minute) % len(maintenance_sample)
    row = maintenance_sample.iloc[row_idx]

    X = row[MAINTENANCE_FEATURE_COLS].values.reshape(1, -1)
    failure_prob = float(maintenance_model.predict_proba(X)[0][1])
    risk_level = "high" if failure_prob > 0.5 else "low"

    row = row.copy()
    row["high_risk"] = 1 if risk_level == "high" else 0
    fault_type, recommendation, urgency, zone_id, criticality_tier = _diagnose_maintenance_row(row)

    return {
        "failure_probability": failure_prob,
        "risk_level": risk_level,
        "transformer_id": str(row["transformer_id"]),
        "zone_id": zone_id,
        "criticality_tier": criticality_tier,
        "fault_type": fault_type,
        "recommendation": recommendation,
        "urgency": urgency,
        "actual_oil_temp": float(row["OT"]),
        "source": "historical_ett_sample",
        "source_note": "Real historical transformer data (ETTm1/ETTm2), not a live sensor reading - this pipeline has no live oil-temperature/load stream."
    }


@app.get("/equipment")
def get_equipment():
    results = []
    for _, row in maintenance_sample.head(6).iterrows():
        X = row[MAINTENANCE_FEATURE_COLS].values.reshape(1, -1)
        failure_prob = float(maintenance_model.predict_proba(X)[0][1])
        health = round((1 - failure_prob) * 100, 1)
        risk_level = "high" if failure_prob > 0.5 else "low"

        row = row.copy()
        row["high_risk"] = 1 if risk_level == "high" else 0
        fault_type, recommendation, urgency, zone_id, criticality_tier = _diagnose_maintenance_row(row)

        results.append({
            "name": f"Transformer {row['transformer_id']} ({row['date']})",
            "zone": zone_id,
            "criticality_tier": criticality_tier,
            "health": health,
            "actual_oil_temp": float(row["OT"]),
            "status": "bad" if health < 70 else "mid" if health < 90 else "good",
            "fault_type": fault_type,
            "recommendation": recommendation,
            "urgency": urgency,
            "source": "historical_ett_sample"
        })

    return {
        "equipment": results,
        "source_note": "Real historical transformer data (ETTm1/ETTm2), not live sensors - this pipeline has no live oil-temperature/load stream."
    }


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

    available = [c for c in FORECAST_FEATURE_COLS if c in df_feat.columns]
    if len(available) != len(FORECAST_FEATURE_COLS):
        return fallback_forecast_metrics("live features missing columns the model needs")

    target_col = "Global_active_power"
    X = df_feat[FORECAST_FEATURE_COLS].values
    y_true = df_feat[target_col].values
    X_scaled = forecast_scaler.transform(X)
    X_reshaped = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
    y_pred = lstm_model.predict(X_reshaped, verbose=0).flatten()

    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-6))) * 100)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    peak_forecast = float(np.max(y_pred))
    drift = float(abs(np.mean(y_pred) - np.mean(y_true)) / max(np.mean(y_true), 1e-6) * 100)

    # Real actual-vs-predicted series (last 30 points) for the UI chart -
    # replaces the previously-simulated "accuracy by horizon" bar chart.
    n_show = min(30, len(df_feat))
    series = [
        {"timestamp": str(idx), "actual": float(a), "predicted": float(p)}
        for idx, a, p in zip(df_feat.index[-n_show:], y_true[-n_show:], y_pred[-n_show:])
    ]

    return {
        "mape_24h": mape,
        "r2_score": r2,
        "peak_forecast": peak_forecast,
        "model_drift": drift,
        "feeder_id": str(target_feeder),
        "source": "live_influxdb",
        "series": series
    }


def fallback_forecast_metrics(reason):
    target_col = "target_30min"
    sample_df = test_df.head(500).copy()
    X_test = sample_df[FORECAST_FEATURE_COLS].values
    y_true = sample_df[target_col].values
    X_scaled = forecast_scaler.transform(X_test)
    X_reshaped = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
    y_pred = lstm_model.predict(X_reshaped, verbose=0).flatten()

    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-6))) * 100)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

    n_show = min(30, len(sample_df))
    series = [
        {"timestamp": str(sample_df.index[i]), "actual": float(y_true[i]), "predicted": float(y_pred[i])}
        for i in range(len(sample_df) - n_show, len(sample_df))
    ]

    return {
        "mape_24h": mape,
        "r2_score": r2,
        "peak_forecast": float(np.max(y_pred)),
        "model_drift": 0.0,
        "source": "static_fallback",
        "reason": reason,
        "series": series
    }


@app.get("/anomalies/stats")
def get_anomaly_stats():
    df = fetch_live_readings(limit=500)
    if df.empty or "feeder_id" not in df.columns:
        return {
            "open_count": 0,
            "critical_unresolved": 0,
            "mean_time_to_detect_sec": None,
            "false_positive_rate": round((1 - autoencoder_config.get("precision", 0)) * 100, 1),
            "resolved_30d": 0,
            "resolved_note": "No resolution workflow implemented yet - always 0",
            "source": "no live data"
        }

    open_count = 0
    critical_count = 0
    timestamps = []

    for feeder_id, group in df.groupby("feeder_id"):
        group = group.sort_index()
        df_feat = build_features(group)
        if df_feat.empty:
            continue

        anomalous_rows = detect_anomalies(df_feat)
        open_count += len(anomalous_rows)

        for idx, row in anomalous_rows.iterrows():
            voltage = row["Voltage"]
            deviation_pct = abs(voltage - 230) / 230 * 100
            if deviation_pct > 3:
                critical_count += 1
            timestamps.append(idx)

    mean_gap_sec = None
    if len(timestamps) > 1:
        timestamps = sorted(timestamps)
        gaps = [(timestamps[i + 1] - timestamps[i]).total_seconds() for i in range(len(timestamps) - 1)]
        mean_gap_sec = int(sum(gaps) / len(gaps))

    real_precision = autoencoder_config.get("precision", 0)
    false_positive_rate = round((1 - real_precision) * 100, 1)

    return {
        "open_count": open_count,
        "critical_unresolved": critical_count,
        "mean_time_to_detect_sec": mean_gap_sec,
        "mean_time_to_detect_note": "Approximate gap between flagged events in the current live window, not a true incident-detection latency measurement",
        "false_positive_rate": false_positive_rate,
        "false_positive_rate_note": f"Derived from measured precision ({real_precision:.3f}) on the synthetic injected-anomaly evaluation set (autoencoder, window={ANOMALY_WINDOW})",
        "resolved_30d": 0,
        "resolved_note": "No resolution workflow implemented yet - always 0",
        "source": "live_influxdb"
    }


@app.get("/feeders")
def get_feeders():
    df = fetch_live_readings(limit=500)
    if df.empty or "feeder_id" not in df.columns:
        raise HTTPException(status_code=503, detail="No live feeder data available yet")

    latest_per_feeder = df.sort_index().groupby("feeder_id").tail(1)

    def get_status(voltage):
        if voltage < 0.92 * 230 or voltage > 1.06 * 230:
            return "CRITICAL"
        if voltage < 0.96 * 230 or voltage > 1.04 * 230:
            return "WATCH"
        return "NOMINAL"

    result = []
    for _, row in latest_per_feeder.iterrows():
        fid = row["feeder_id"]
        zone_id, criticality_tier, facility_type = _zone_lookup(fid)
        voltage = float(row.get("Voltage", 230))
        current = float(row.get("Global_intensity", 0))
        power = float(row.get("Global_active_power", 0))
        reactive = float(row.get("Global_reactive_power", 0))
        apparent = (power ** 2 + reactive ** 2) ** 0.5
        pf = round(power / apparent, 2) if apparent > 0 else 1.0

        result.append({
            "name": f"FDR-{fid}",
            "zone": zone_id,
            "criticality_tier": criticality_tier,
            "facility_type": facility_type,
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

    zone_meta = {}
    for z in zones_all:
        zdf = feeder_zone_df[feeder_zone_df["zone_id"] == z]
        tier_mode = zdf["criticality_tier"].mode()
        facility_mode = zdf["facility_type"].mode()
        zone_meta[z] = {
            "criticality_tier": tier_mode.iloc[0] if not tier_mode.empty else "Low",
            "facility_type": facility_mode.iloc[0] if not facility_mode.empty else "Unassigned",
        }

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
            settings = load_settings()
            nominal = 230
            critical_band = settings["voltage_critical_pct"] / 100
            warning_band = settings["voltage_warning_pct"] / 100
            if voltage < nominal * (1 - critical_band) or voltage > nominal * (1 + critical_band):
                status = "critical"
            elif voltage < nominal * (1 - warning_band) or voltage > nominal * (1 + warning_band):
                status = "watch"
            else:
                status = "nominal"

            if severity_rank[status] > severity_rank[zone_status[zone_id]]:
                zone_status[zone_id] = status

    return {
        "zones": [
            {
                "zone_id": z,
                "status": s,
                "criticality_tier": zone_meta[z]["criticality_tier"],
                "facility_type": zone_meta[z]["facility_type"],
            }
            for z, s in zone_status.items()
        ]
    }


@app.get("/anomalies/queue")
def get_anomaly_queue():
    df = fetch_live_readings(limit=500)
    if df.empty or "feeder_id" not in df.columns:
        return []

    queue = []
    for feeder_id, group in df.groupby("feeder_id"):
        group = group.sort_index()
        df_feat = build_features(group)
        if df_feat.empty:
            continue

        anomalous_rows = detect_anomalies(df_feat)
        zone_id, criticality_tier, facility_type = _zone_lookup(feeder_id)

        for idx, row in anomalous_rows.tail(5).iterrows():
            voltage = row["Voltage"]
            deviation_pct = abs(voltage - 230) / 230 * 100
            settings = load_settings()
            severity = (
                "CRITICAL" if deviation_pct > settings["voltage_critical_pct"]
                else "WARNING" if deviation_pct > settings["voltage_warning_pct"]
                else "INFO"
            )

            queue.append({
                "id": f"ANM-{feeder_id}-{idx.strftime('%H%M%S')}",
                "type": "Autoencoder reconstruction anomaly",
                "asset": f"Feeder {feeder_id}",
                "zone": zone_id,
                "criticality_tier": criticality_tier,
                "facility_type": facility_type,
                "severity": severity,
                "timestamp": str(idx),
                "active_power": round(float(row["Global_active_power"]), 2),
                "voltage": round(float(voltage), 1),
                "deviation_pct": round(float(deviation_pct), 2),
                "reconstruction_error": round(float(row["reconstruction_error"]), 5),
                "status": "Open",
            })

    queue.sort(key=lambda x: x["timestamp"], reverse=True)
    top_queue = queue[:20]
    alerts.check_and_send_anomaly_alerts(top_queue)
    return top_queue


@app.get("/settings")
def get_settings():
    return load_settings()


@app.post("/settings")
def update_settings(new_settings: dict):
    current = load_settings()
    current.update(new_settings)
    save_settings(current)
    return {"status": "saved", "settings": current}


@app.get("/reports/reliability")
def get_reliability_report():
    if not os.path.exists(FAULTS_PATH):
        raise HTTPException(status_code=404, detail="Live Faults CSV not found - check data/raw/faults/")

    df = pd.read_csv(FAULTS_PATH)
    total_incidents = len(df)

    def safe_sum(df, col):
        if col not in df.columns or df[col].isna().all():
            return "N/A"
        return int(pd.to_numeric(df[col], errors='coerce').fillna(0).sum())

    unplanned = safe_sum(df, "UnplannedIncidents")
    planned = safe_sum(df, "PlannedIncidents")
    customers_affected = safe_sum(df, "NoCustomerAffected")

    by_category = (
        df["IncidentCategoryCustomerFriendlyDescription"].value_counts().to_dict()
        if "IncidentCategoryCustomerFriendlyDescription" in df.columns else {}
    )

    return {
        "report_type": "Reliability & Incident Summary (real UKPN fault data)",
        "total_incidents": total_incidents,
        "unplanned_incidents": unplanned,
        "planned_incidents": planned,
        "customers_affected": customers_affected,
        "incidents_by_category": by_category,
        "note": "Generated from real UKPN Live Faults data. Not a formal SAIDI/SAIFI calculation, which requires total customers served as an additional input."
    }


@app.get("/reports/forecast-backtest")
def get_forecast_backtest_report():
    metrics = get_forecast_metrics()
    return {
        "report_type": "Forecast Performance Backtest",
        **metrics
    }


@app.get("/reports/anomaly-log")
def get_anomaly_log_report():
    queue = get_anomaly_queue()
    return {
        "report_type": "Anomaly Incident Log",
        "generated_at": str(pd.Timestamp.now()),
        "entries": queue
    }