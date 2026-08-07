import os
import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Input

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "feeder_stream.csv")
MODELS_DIR = os.path.join(BASE_DIR, "forecasting")
FALLBACK_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "test_uci_household.csv")

def build_features(df):
    df = df.copy()
    df["hour"] = df.index.hour
    df["day_of_week"] = df.index.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)

    target = "Global_active_power"
    for lag in [1, 2, 3, 6, 12]:
        df[f"{target}_lag_{lag}"] = df[target].shift(lag)
    for window in [3, 6, 12]:
        df[f"{target}_roll_mean_{window}"] = df[target].shift(1).rolling(window).mean()
        df[f"{target}_roll_std_{window}"] = df[target].shift(1).rolling(window).std()

    # Sub_metering placeholders
    for sm in ["Sub_metering_1", "Sub_metering_2", "Sub_metering_3"]:
        df[sm] = 0.0

    df["pct_change"] = df[target].pct_change().fillna(0)
    df["expected_for_hour"] = df.groupby("hour")[target].transform("mean")
    df["deviation_from_hourly_norm"] = df[target] - df["expected_for_hour"]

    return df.drop(columns=["anomaly_type", "is_injected_anomaly"], errors="ignore").dropna()

def main():
    print("Loading data...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df = df.rename(columns={
        "active_power": "Global_active_power",
        "voltage": "Voltage",
        "current": "Global_intensity",
        "reactive_power": "Global_reactive_power"
    })
    
    # Resample per feeder group to 5 minutes and interpolate
    print("Resampling and interpolating to 5-minute resolution...")
    processed_dfs = []
    for feeder_id, group in df.groupby("feeder_id"):
        group = group.set_index("timestamp")
        group = group.resample("5Min").mean(numeric_only=True)
        group["Global_active_power"] = group["Global_active_power"].interpolate()
        group["Voltage"] = group["Voltage"].interpolate()
        group["Global_intensity"] = group["Global_intensity"].interpolate()
        group["Global_reactive_power"] = group["Global_reactive_power"].interpolate()
        group = group.ffill().bfill()
        processed_dfs.append(group)
        
    df_resampled = pd.concat(processed_dfs).sort_index()
    
    print("Engineering features...")
    df_feat = build_features(df_resampled)
    
    # Target variables
    df_feat["target_5min"] = df_feat["Global_active_power"].shift(-1)
    df_feat["target_15min"] = df_feat["Global_active_power"].shift(-3)
    df_feat["target_30min"] = df_feat["Global_active_power"].shift(-6)
    df_feat = df_feat.dropna()
    
    # Select feature columns (excluding target_*)
    feature_cols = [
        "Global_active_power", "Global_reactive_power", "Voltage", "Global_intensity",
        "Sub_metering_1", "Sub_metering_2", "Sub_metering_3",
        "Global_active_power_lag_1", "Global_active_power_lag_2", "Global_active_power_lag_3",
        "Global_active_power_lag_6", "Global_active_power_lag_12",
        "Global_active_power_roll_mean_3", "Global_active_power_roll_std_3",
        "Global_active_power_roll_mean_6", "Global_active_power_roll_std_6",
        "Global_active_power_roll_mean_12", "Global_active_power_roll_std_12",
        "hour", "day_of_week", "is_weekend", "hour_sin", "hour_cos"
    ]
    
    X = df_feat[feature_cols].values
    y = df_feat["target_5min"].values
    
    # Train-test split (chronological)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    
    # Save the test set as fallback test_uci_household.csv
    print(f"Saving test fallback to {FALLBACK_PATH}...")
    # Add target_ columns back to match expected schema exactly
    test_df_save = df_feat.iloc[split_idx:].copy()
    test_df_save.index.name = "datetime"
    # Ensure it only has the required columns
    all_cols = feature_cols + ["target_5min", "target_15min", "target_30min"]
    test_df_save[all_cols].to_csv(FALLBACK_PATH)
    
    # Reshape for LSTM: [samples, timesteps=1, features]
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
    model.fit(X_train_reshaped, y_train, epochs=3, batch_size=64, validation_split=0.1, verbose=1)
    
    # Evaluate
    loss = model.evaluate(X_test_reshaped, y_test, verbose=0)
    print(f"Test MSE Loss: {loss:.4f}")
    
    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "lstm_baseline_5min.keras")
    model.save(model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    main()
