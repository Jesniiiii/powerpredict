import os
import json
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Input
from tensorflow.keras.callbacks import EarlyStopping

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "feeder_stream.csv")
MODELS_DIR = os.path.join(BASE_DIR, "forecasting")
FALLBACK_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "test_uci_household.csv")


def build_features(df):
    """Per-feeder feature engineering, grouped by feeder_uid (the real unique
    physical feeder key - feeder_id alone repeats across substations, see
    build_feeder_stream.py). A feeder's lag-1 value is always its own previous
    reading, never another feeder's value that happened to share a feeder_id."""
    df = df.copy()
    df["hour"] = df.index.hour
    df["day_of_week"] = df.index.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    target = "Global_active_power"
    grp = df.groupby("feeder_uid")[target]

    for lag in [1, 2, 3, 6, 12]:
        df[f"{target}_lag_{lag}"] = grp.shift(lag)
    for window in [3, 6, 12]:
        df[f"{target}_roll_mean_{window}"] = df.groupby("feeder_uid")[target].transform(
            lambda s: s.shift(1).rolling(window).mean())
        df[f"{target}_roll_std_{window}"] = df.groupby("feeder_uid")[target].transform(
            lambda s: s.shift(1).rolling(window).std())

    df["pct_change"] = df.groupby("feeder_uid")[target].pct_change().fillna(0)
    df["expected_for_hour"] = df.groupby(["feeder_uid", "hour"])[target].transform("mean")
    df["deviation_from_hourly_norm"] = df[target] - df["expected_for_hour"]

    return df.drop(columns=["anomaly_type", "is_injected_anomaly"], errors="ignore").dropna()


def per_feeder_chronological_split(df, feeder_col="feeder_uid", test_frac=0.2):
    """Splits chronologically WITHIN each feeder (last test_frac of each feeder's
    own timeline goes to test), rather than a single global split point. This
    avoids one feeder's early data training on another feeder's later data,
    while still respecting time order per feeder."""
    train_parts, test_parts = [], []
    for _, group in df.groupby(feeder_col):
        group = group.sort_index()
        split_idx = int(len(group) * (1 - test_frac))
        train_parts.append(group.iloc[:split_idx])
        test_parts.append(group.iloc[split_idx:])
    train_df = pd.concat(train_parts).sort_index()
    test_df = pd.concat(test_parts).sort_index()
    return train_df, test_df


def main():
    print("Loading data...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df = df.rename(columns={
        "active_power": "Global_active_power",
        "voltage": "Voltage",
        "current": "Global_intensity",
        "reactive_power": "Global_reactive_power"
    })

    # NOTE: no resampling/interpolation here. The real native UKPN cadence in
    # feeder_stream.csv is 30 minutes (verified via check_cadence.py) - training
    # and evaluating on that directly, not on an artificially interpolated finer
    # grid, which was previously found to give misleadingly inflated R2/MAPE.
    print("Setting datetime index per feeder (native ~30-min cadence, no interpolation)...")
    df = df.sort_values(["feeder_uid", "timestamp"]).set_index("timestamp")

    print("Engineering features (grouped per feeder_uid)...")
    df_feat = build_features(df)

    # Horizons redefined in real 30-min steps (native cadence), not the old fake
    # 5/15/30-min grid built on interpolated data. target_30min = next real
    # reading (1 step ahead) - this is the primary training target, same as before.
    df_feat["target_30min"] = df_feat.groupby("feeder_uid")["Global_active_power"].shift(-1)
    df_feat["target_60min"] = df_feat.groupby("feeder_uid")["Global_active_power"].shift(-2)
    df_feat["target_90min"] = df_feat.groupby("feeder_uid")["Global_active_power"].shift(-3)
    df_feat = df_feat.dropna()

    feature_cols = [
        "Global_active_power", "Global_reactive_power", "Voltage", "Global_intensity",
        "Global_active_power_lag_1", "Global_active_power_lag_2", "Global_active_power_lag_3",
        "Global_active_power_lag_6", "Global_active_power_lag_12",
        "Global_active_power_roll_mean_3", "Global_active_power_roll_std_3",
        "Global_active_power_roll_mean_6", "Global_active_power_roll_std_6",
        "Global_active_power_roll_mean_12", "Global_active_power_roll_std_12",
        "hour", "day_of_week", "is_weekend", "hour_sin", "hour_cos"
    ]
    target_col = "target_30min"

    print("Splitting train/test per feeder (chronological within each feeder)...")
    train_df, test_df = per_feeder_chronological_split(df_feat, test_frac=0.2)
    print(f"Train: {len(train_df)} rows | Test: {len(test_df)} rows")

    X_train_raw = train_df[feature_cols].values
    X_test_raw = test_df[feature_cols].values
    y_train = train_df[target_col].values
    y_test = test_df[target_col].values

    print("Fitting scaler on training data...")
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw)
    X_test = scaler.transform(X_test_raw)

    print(f"Saving test fallback to {FALLBACK_PATH}...")
    test_fallback = test_df.copy()
    test_fallback.index.name = "datetime"
    all_cols = feature_cols + ["feeder_uid", "target_30min", "target_60min", "target_90min"]
    test_fallback[all_cols].to_csv(FALLBACK_PATH)

    X_train_reshaped = X_train.reshape((X_train.shape[0], 1, X_train.shape[1]))
    X_test_reshaped = X_test.reshape((X_test.shape[0], 1, X_test.shape[1]))

    print(f"Training LSTM forecasting model on {X_train.shape[0]} samples...")
    model = Sequential([
        Input(shape=(1, X_train.shape[1])),
        LSTM(64, activation='relu', return_sequences=False),
        Dense(32, activation='relu'),
        Dense(1)
    ])

    model.compile(optimizer='adam', loss='mse')

    early_stop = EarlyStopping(monitor='val_loss', patience=8, restore_best_weights=True)
    model.fit(
        X_train_reshaped, y_train,
        epochs=100, batch_size=64,
        validation_split=0.1,
        callbacks=[early_stop],
        verbose=1
    )

    y_pred = model.predict(X_test_reshaped, verbose=0).flatten()
    mape = float(np.mean(np.abs((y_test - y_pred) / np.maximum(y_test, 1e-6))) * 100)
    ss_res = np.sum((y_test - y_pred) ** 2)
    ss_tot = np.sum((y_test - np.mean(y_test)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    mse = model.evaluate(X_test_reshaped, y_test, verbose=0)

    print(f"\n--- Held-out test set evaluation (native 30-min cadence) ---")
    print(f"Test MSE:  {mse:.4f}")
    print(f"Test MAPE: {mape:.2f}%")
    print(f"Test R2:   {r2:.4f}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "lstm_baseline_30min.keras")
    scaler_path = os.path.join(MODELS_DIR, "forecast_scaler.pkl")
    config_path = os.path.join(MODELS_DIR, "forecast_config.json")

    model.save(model_path)
    joblib.dump(scaler, scaler_path)
    with open(config_path, "w") as f:
        json.dump({
            "feature_cols": feature_cols,
            "target_col": target_col,
            "window_size": 1,
            "cadence_minutes": 30,
            "test_mape": mape,
            "test_r2": r2,
        }, f, indent=2)

    print(f"\nModel saved to {model_path}")
    print(f"Scaler saved to {scaler_path}")
    print(f"Config saved to {config_path}")


if __name__ == "__main__":
    main()