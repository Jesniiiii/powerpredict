import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, RepeatVector, TimeDistributed, Dense, Input
from tensorflow.keras.callbacks import EarlyStopping

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "feeder_stream_injected.csv")
MODELS_DIR = os.path.join(BASE_DIR, "anomaly")

WINDOW = 6                 # sequence length per sample
THRESHOLD_PERCENTILE = 97  # reconstruction error above this percentile (on clean
                            # training data) is flagged anomalous - avoids guessing
                            # a raw contamination fraction like Isolation Forest needed


def build_features(df):
    """Same per-feeder feature engineering as train_anomaly.py, for a fair
    comparison against Isolation Forest using the same validated features.
    Grouped by feeder_uid, the real unique physical feeder key (feeder_id
    alone repeats across substations - see build_feeder_stream.py)."""
    df = df.copy()
    df["hour"] = df.index.hour
    target = "Global_active_power"

    df["pct_change"] = df.groupby("feeder_uid")[target].pct_change().fillna(0)
    df["expected_for_hour"] = df.groupby(["feeder_uid", "hour"])[target].transform("mean")
    df["deviation_from_hourly_norm"] = df[target] - df["expected_for_hour"]

    feeder_std = df.groupby("feeder_uid")[target].transform("std")
    feeder_mean = df.groupby("feeder_uid")[target].transform("mean")
    df["deviation_zscore"] = (df["deviation_from_hourly_norm"] / feeder_std.replace(0, np.nan)).fillna(0)
    df["power_zscore"] = ((df[target] - feeder_mean) / feeder_std.replace(0, np.nan)).fillna(0)

    return df


def build_windows(df, feature_cols, window):
    """Builds sliding windows per feeder (grouped by feeder_uid, the real unique
    physical feeder key). Returns X (n_windows, window, n_features), and a
    boolean array marking whether ANY row in each window was an injected
    anomaly (used only for evaluation, never as a training input)."""
    X, is_anomalous, feeder_uids, end_timestamps = [], [], [], []
    for feeder_uid, group in df.groupby("feeder_uid"):
        group = group.sort_index()
        feats = group[feature_cols].values
        anomaly_flags = group["is_injected_anomaly"].values
        for i in range(len(group) - window + 1):
            X.append(feats[i:i + window])
            is_anomalous.append(bool(anomaly_flags[i:i + window].any()))
            feeder_uids.append(feeder_uid)
            end_timestamps.append(group.index[i + window - 1])
    return np.array(X), np.array(is_anomalous), feeder_uids, end_timestamps


def main():
    print("Loading injected feeder stream data...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df = df.rename(columns={
        "active_power": "Global_active_power",
        "voltage": "Voltage",
        "current": "Global_intensity",
        "reactive_power": "Global_reactive_power"
    })
    df = df.set_index("timestamp").sort_index()

    print("Engineering features...")
    df_feat = build_features(df)
    feature_cols = ["pct_change", "deviation_zscore", "power_zscore", "Voltage", "Global_reactive_power"]

    print(f"Building sliding windows (length {WINDOW})...")
    X_all, is_anomalous, feeder_uids, timestamps = build_windows(df_feat, feature_cols, WINDOW)
    print(f"Total windows: {len(X_all)} | Anomalous windows: {is_anomalous.sum()} ({is_anomalous.mean()*100:.2f}%)")

    # Train only on clean windows - the model should never see an injected
    # anomaly during training, so anomalous patterns reconstruct poorly later
    clean_idx = ~is_anomalous
    X_clean = X_all[clean_idx]

    # Scale using only clean data statistics
    scaler = StandardScaler()
    n_samples, window, n_features = X_clean.shape
    X_clean_scaled = scaler.fit_transform(X_clean.reshape(-1, n_features)).reshape(n_samples, window,n_features)

    # Split clean windows into train/val (for early stopping) and a held-out
    # clean portion (for setting the reconstruction-error threshold honestly,
    # not on data the model trained on)
    split = int(len(X_clean_scaled) * 0.8)
    X_train = X_clean_scaled[:split]
    X_threshold_calib = X_clean_scaled[split:]

    print(f"Training LSTM autoencoder on {len(X_train)} clean windows...")
    model = Sequential([
        Input(shape=(WINDOW, n_features)),
        LSTM(32, activation='relu', return_sequences=False),
        RepeatVector(WINDOW),
        LSTM(32, activation='relu', return_sequences=True),
        TimeDistributed(Dense(n_features))
    ])
    model.compile(optimizer='adam', loss='mse')
    early_stop = EarlyStopping(monitor='val_loss', patience=8, restore_best_weights=True)
    model.fit(
        X_train, X_train,
        epochs=100, batch_size=32,
        validation_split=0.1,
        callbacks=[early_stop],
        verbose=1
    )

    def reconstruction_error(X):
        recon = model.predict(X, verbose=0)
        return np.mean(np.square(X - recon), axis=(1, 2))

    print("Calibrating threshold on held-out clean data...")
    calib_errors = reconstruction_error(X_threshold_calib)
    threshold = float(np.percentile(calib_errors, THRESHOLD_PERCENTILE))
    print(f"Reconstruction error threshold ({THRESHOLD_PERCENTILE}th percentile of clean data): {threshold:.5f}")

    print("Evaluating against ALL windows (clean + injected anomalies)...")
    X_all_scaled = scaler.transform(X_all.reshape(-1, n_features)).reshape(len(X_all), WINDOW, n_features)
    all_errors = reconstruction_error(X_all_scaled)
    y_pred = (all_errors > threshold).astype(int)
    y_true = is_anomalous.astype(int)

    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
    cm = confusion_matrix(y_true, y_pred)

    print(f"\n--- Autoencoder evaluation (window-level, W={WINDOW}) ---")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-score:  {f1:.4f}")
    print(f"Confusion matrix:\n{cm}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    model.save(os.path.join(MODELS_DIR, "lstm_autoencoder.keras"))
    joblib.dump(scaler, os.path.join(MODELS_DIR, "autoencoder_scaler.pkl"))
    with open(os.path.join(MODELS_DIR, "autoencoder_config.json"), "w") as f:
        json.dump({
            "feature_cols": feature_cols,
            "window": WINDOW,
            "threshold": threshold,
            "threshold_percentile": THRESHOLD_PERCENTILE,
            "precision": precision,
            "recall": recall,
            "f1_score": f1
        }, f, indent=2)

    print(f"\nModel, scaler, and config saved to {MODELS_DIR}")


if __name__ == "__main__":
    main()