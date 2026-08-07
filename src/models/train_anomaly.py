import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, precision_recall_fscore_support

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "feeder_stream_injected.csv")
MODELS_DIR = os.path.join(BASE_DIR, "anomaly")

def build_features(df):
    df = df.copy()
    df["hour"] = df.index.hour
    target = "Global_active_power"

    df["pct_change"] = df.groupby("feeder_id")[target].pct_change().fillna(0)
    df["expected_for_hour"] = df.groupby(["feeder_id", "hour"])[target].transform("mean")
    df["deviation_from_hourly_norm"] = df[target] - df["expected_for_hour"]

    feeder_std = df.groupby("feeder_id")[target].transform("std")
    df["deviation_zscore"] = (df["deviation_from_hourly_norm"] / feeder_std.replace(0, np.nan)).fillna(0)

    # NEW: the power level itself, z-scored per feeder - directly captures spikes/drift
    # that pct_change and hourly-deviation might miss against natural feeder volatility
    feeder_mean = df.groupby("feeder_id")[target].transform("mean")
    df["power_zscore"] = ((df[target] - feeder_mean) / feeder_std.replace(0, np.nan)).fillna(0)

    return df

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

    # FIXED: use the z-score feature instead of the raw (unscaled-across-feeders) deviation
    feature_cols = ["pct_change", "deviation_zscore", "power_zscore", "Voltage", "Global_reactive_power"]

    # We train Isolation Forest on CLEAN data
    train_data = df_feat[df_feat["is_injected_anomaly"] == False]
    X_train = train_data[feature_cols].values

    print(f"Training StandardScaler on clean data ({X_train.shape[0]} rows)...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    print("Training IsolationForest model...")
    # contamination set to ~1.5%, matching the real injected anomaly rate in this dataset
    iso_forest = IsolationForest(n_estimators=100, contamination=0.015, random_state=42)
    iso_forest.fit(X_train_scaled)

    # Evaluate against the whole dataset containing injected anomalies
    print("Evaluating model against injected anomalies...")
    X_all = df_feat[feature_cols].values
    y_true = df_feat["is_injected_anomaly"].values.astype(int)  # True (1) = anomaly, False (0) = normal

    X_all_scaled = scaler.transform(X_all)
    preds = iso_forest.predict(X_all_scaled)  # -1 = anomaly, 1 = normal
    y_pred = (preds == -1).astype(int)  # Convert to 1 = anomaly, 0 = normal

    df_feat["y_pred"] = y_pred
    print("\nRecall by anomaly type:")
    for atype in df_feat[df_feat["is_injected_anomaly"]]["anomaly_type"].unique():
        mask = df_feat["anomaly_type"] == atype
        detected = (df_feat.loc[mask, "y_pred"] == 1).sum()
        total = mask.sum()
        print(f"  {atype}: {detected}/{total} ({detected/total*100:.1f}%)")


    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='binary')
    print(f"\nEvaluation Results:")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1-Score: {f1:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=["Normal", "Anomaly"]))

    # Save artifacts
    os.makedirs(MODELS_DIR, exist_ok=True)
    scaler_path = os.path.join(MODELS_DIR, "anomaly_scaler.pkl")
    model_path = os.path.join(MODELS_DIR, "isolation_forest.pkl")
    metrics_path = os.path.join(MODELS_DIR, "synthetic_eval_results.json")

    joblib.dump(scaler, scaler_path)
    joblib.dump(iso_forest, model_path)

    eval_metrics = {
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "anomaly_count_detected": int((y_pred == 1).sum()),
        "ground_truth_count": int(y_true.sum())
    }
    with open(metrics_path, "w") as f:
        json.dump(eval_metrics, f, indent=4)

    print(f"Scaler saved to {scaler_path}")
    print(f"Isolation Forest saved to {model_path}")
    print(f"Evaluation metrics saved to {metrics_path}")

if __name__ == "__main__":
    main()