"""
inject_anomalies.py

Creates data/processed/feeder_stream_injected.csv and
data/processed/anomaly_injection_log.csv

Takes the clean feeder_stream.csv and injects labeled synthetic anomaly windows
(voltage dip, load spike, sensor dropout, slow drift) so Isolation Forest / the
LSTM autoencoder can be evaluated against real ground truth. The original
feeder_stream.csv is left untouched - use the injected version for training/eval,
the clean version for the live replay demo.

Expected location: src/etl/inject_anomalies.py
"""

import os
import numpy as np
import pandas as pd

# ---- CONFIG ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "data")

INPUT_PATH = os.path.join(DATA_ROOT, "processed", "feeder_stream.csv")
OUTPUT_STREAM_PATH = os.path.join(DATA_ROOT, "processed", "feeder_stream_injected.csv")
OUTPUT_LOG_PATH = os.path.join(DATA_ROOT, "processed", "anomaly_injection_log.csv")

N_WINDOWS = 40          # number of anomaly windows to inject
MIN_WINDOW_ROWS = 3     # minimum consecutive readings per window (~1.5h at 30-min intervals)
MAX_WINDOW_ROWS = 12    # maximum consecutive readings per window (~6h)

RANDOM_SEED = 42

ANOMALY_TYPES = ["voltage_dip", "load_spike", "sensor_dropout", "slow_drift"]
# --------------------------------------------------------------------


def inject_voltage_dip(df, idx):
    factor = np.random.uniform(0.85, 0.92)
    df.loc[idx, "voltage"] = df.loc[idx, "voltage"] * factor
    return factor


def inject_load_spike(df, idx):
    factor = np.random.uniform(1.2, 1.4)
    df.loc[idx, "active_power"] = df.loc[idx, "active_power"] * factor
    df.loc[idx, "current"] = df.loc[idx, "current"] * factor
    return factor


def inject_sensor_dropout(df, idx):
    # flatline at the last good value before the window (simulates a stuck/dead sensor)
    first_idx = idx[0]
    flat_power = df.loc[first_idx, "active_power"]
    flat_voltage = df.loc[first_idx, "voltage"]
    df.loc[idx, "active_power"] = flat_power
    df.loc[idx, "voltage"] = flat_voltage
    df.loc[idx, "current"] = df.loc[first_idx, "current"]
    return 0.0  # no meaningful "magnitude" for a flatline


def inject_slow_drift(df, idx):
    # linear ramp down in active_power over the window - simulates gradual theft/degradation
    n = len(idx)
    ramp = np.linspace(1.0, np.random.uniform(0.5, 0.75), n)
    df.loc[idx, "active_power"] = df.loc[idx, "active_power"].values * ramp
    return ramp[-1]


INJECTORS = {
    "voltage_dip": inject_voltage_dip,
    "load_spike": inject_load_spike,
    "sensor_dropout": inject_sensor_dropout,
    "slow_drift": inject_slow_drift,
}


def main():
    np.random.seed(RANDOM_SEED)

    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"{INPUT_PATH} not found - run build_feeder_stream.py first.")

    df = pd.read_csv(INPUT_PATH, parse_dates=["timestamp"])
    df["anomaly_type"] = df["anomaly_type"].astype(object)
    df = df.sort_values(["feeder_id", "timestamp"]).reset_index(drop=True)

    print(f"Loaded {len(df)} clean readings across {df['feeder_id'].nunique()} feeders")

    feeder_groups = {fid: grp.index.tolist() for fid, grp in df.groupby("feeder_id")}
    feeder_ids = list(feeder_groups.keys())

    log_rows = []
    injected_count = 0
    attempts = 0
    max_attempts = N_WINDOWS * 20  # avoid infinite loop if data is too small/fragmented

    while injected_count < N_WINDOWS and attempts < max_attempts:
        attempts += 1
        feeder_id = np.random.choice(feeder_ids)
        row_indices = feeder_groups[feeder_id]

        window_len = np.random.randint(MIN_WINDOW_ROWS, MAX_WINDOW_ROWS + 1)
        if len(row_indices) <= window_len:
            continue

        start_pos = np.random.randint(0, len(row_indices) - window_len)
        window_idx = row_indices[start_pos: start_pos + window_len]

        # skip if this window overlaps an already-injected window (avoid double-injecting)
        if df.loc[window_idx, "is_injected_anomaly"].any():
            continue

        anomaly_type = np.random.choice(ANOMALY_TYPES)
        magnitude = INJECTORS[anomaly_type](df, window_idx)

        df.loc[window_idx, "is_injected_anomaly"] = True
        df.loc[window_idx, "anomaly_type"] = anomaly_type

        log_rows.append({
            "feeder_id": feeder_id,
            "anomaly_type": anomaly_type,
            "start_time": df.loc[window_idx[0], "timestamp"],
            "end_time": df.loc[window_idx[-1], "timestamp"],
            "n_rows": window_len,
            "magnitude": magnitude,
        })
        injected_count += 1

    if injected_count < N_WINDOWS:
        print(f"WARNING: only injected {injected_count}/{N_WINDOWS} windows "
              f"(ran out of non-overlapping space - dataset may be too small). "
              f"Consider lowering N_WINDOWS or MAX_WINDOW_ROWS.")

    log_df = pd.DataFrame(log_rows)

    os.makedirs(os.path.dirname(OUTPUT_STREAM_PATH), exist_ok=True)
    df.to_csv(OUTPUT_STREAM_PATH, index=False)
    log_df.to_csv(OUTPUT_LOG_PATH, index=False)

    n_anomalous_rows = df["is_injected_anomaly"].sum()
    print(f"\nInjected {injected_count} anomaly windows ({n_anomalous_rows} rows, "
          f"{n_anomalous_rows / len(df) * 100:.2f}% of total)")
    print(f"Breakdown by type:")
    print(log_df["anomaly_type"].value_counts().to_string())
    print(f"\nWrote injected stream to {OUTPUT_STREAM_PATH}")
    print(f"Wrote injection log to {OUTPUT_LOG_PATH}")


if __name__ == "__main__":
    main()