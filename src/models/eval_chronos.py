"""
eval_chronos.py

Zero-shot Chronos-Bolt evaluation, matched one-to-one against the LSTM baseline
protocol in train_forecasting.py: same per-feeder chronological 80/20 split,
same one-step-ahead (30-min) target, native cadence, no interpolation.

For every test-period reading, Chronos is given only REAL history strictly
before that point (never its own past predictions) - this matches what the
LSTM's lag/rolling features effectively see, so MAPE/R2 are directly comparable
to the lstm_baseline_30min.keras numbers.

No fine-tuning here - this is zero-shot (no feeder-specific training at all).
Fine-tuning is a separate follow-up step if time allows.

Expected location: src/models/eval_chronos.py
"""

import os
import time
import numpy as np
import pandas as pd
import torch
from chronos import BaseChronosPipeline

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "..", "data", "processed", "feeder_stream.csv")
RESULTS_PATH = os.path.join(BASE_DIR, "forecasting", "chronos_zero_shot_results.json")

MODEL_ID = "amazon/chronos-bolt-small"   # CPU-friendly; swap to -tiny if this is too slow
MAX_CONTEXT = 512                        # cap history fed per prediction (speed/memory)
TEST_FRAC = 0.2                          # must match train_forecasting.py's split


def main():
    print(f"Loading data from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df = df.rename(columns={"active_power": "Global_active_power"})
    df = df.sort_values(["feeder_uid", "timestamp"]).reset_index(drop=True)

    print(f"Loading {MODEL_ID} on CPU (first run downloads the model, ~100-200MB)...")
    t0 = time.time()
    pipeline = BaseChronosPipeline.from_pretrained(
        MODEL_ID, device_map="cpu", torch_dtype=torch.float32
    )
    print(f"Model loaded in {time.time() - t0:.1f}s")

    all_y_true, all_y_pred, all_feeder_uid = [], [], []

    feeder_uids = df["feeder_uid"].unique()
    print(f"\nEvaluating {len(feeder_uids)} feeders, one-step-ahead, zero-shot...")

    for i, feeder_uid in enumerate(feeder_uids):
        group = df[df["feeder_uid"] == feeder_uid].sort_values("timestamp")
        series = group["Global_active_power"].values
        n = len(series)
        split_idx = int(n * (1 - TEST_FRAC))

        if n - split_idx < 5:
            print(f"  [{i+1}/{len(feeder_uids)}] {feeder_uid}: too few test rows ({n - split_idx}), skipping")
            continue

        # Build one context array per test point: real history strictly before it,
        # capped at MAX_CONTEXT points. This is the "one-step-ahead, no leakage"
        # protocol matching the LSTM's lag-feature setup.
        contexts = []
        for t in range(split_idx, n):
            start = max(0, t - MAX_CONTEXT)
            contexts.append(torch.tensor(series[start:t], dtype=torch.float32))

        t0 = time.time()
        quantiles, _ = pipeline.predict_quantiles(
            inputs=contexts, prediction_length=1, quantile_levels=[0.5]
        )
        preds = quantiles[:, 0, 0].numpy()  # median (0.5 quantile) forecast, 1 step ahead
        elapsed = time.time() - t0

        y_true = series[split_idx:n]
        all_y_true.extend(y_true.tolist())
        all_y_pred.extend(preds.tolist())
        all_feeder_uid.extend([feeder_uid] * len(y_true))

        feeder_mape = float(np.mean(np.abs((y_true - preds) / np.maximum(y_true, 1e-6))) * 100)
        print(f"  [{i+1}/{len(feeder_uids)}] {feeder_uid}: {len(y_true)} points, "
              f"MAPE={feeder_mape:.2f}%, took {elapsed:.1f}s")

    y_true = np.array(all_y_true)
    y_pred = np.array(all_y_pred)

    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-6))) * 100)
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    mse = float(np.mean((y_true - y_pred) ** 2))

    print(f"\n--- Chronos-Bolt ZERO-SHOT, one-step-ahead, native 30-min cadence ---")
    print(f"N predictions: {len(y_true)}")
    print(f"Test MSE:  {mse:.4f}")
    print(f"Test MAPE: {mape:.2f}%")
    print(f"Test R2:   {r2:.4f}")

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    import json
    with open(RESULTS_PATH, "w") as f:
        json.dump({
            "model_id": MODEL_ID,
            "mode": "zero_shot",
            "n_predictions": len(y_true),
            "test_mse": mse,
            "test_mape": mape,
            "test_r2": r2,
        }, f, indent=2)
    print(f"\nResults saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()