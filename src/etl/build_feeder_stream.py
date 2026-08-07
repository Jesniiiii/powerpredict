"""
build_feeder_stream.py

Builds data/processed/feeder_stream.csv - the file the replay producer reads.

Does three things:
  1. Joins raw LV feeder consumption data with feeder_zone_map.csv (zone assignment)
  2. Converts half-hourly ENERGY readings (kWh/kVArh) into average POWER (kW/kVAr)
  3. Synthesizes voltage and current, since no real dataset in this pipeline has them.
     This is a documented modeling assumption, not real telemetry - say so in your report.

Expected location: src/etl/build_feeder_stream.py
"""

import os
import glob
import numpy as np
import pandas as pd

# ---- CONFIG ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "data")

LV_FEEDER_DIR = os.path.join(DATA_ROOT, "raw", "ukpn_feeders")
ZONE_MAP_PATH = os.path.join(DATA_ROOT, "processed", "feeder_zone_map.csv")
OUTPUT_PATH = os.path.join(DATA_ROOT, "processed", "feeder_stream.csv")

READING_INTERVAL_HOURS = 0.5  # half-hourly readings -> power = energy / 0.5

# Raw consumption values appear to be in Wh, not kWh, based on magnitude sanity-checking
# (treating them as kWh produced feeder loads in the tens-of-MW range, which is not
# physically plausible for an LV feeder serving a few hundred customers).
# VERIFY THIS against the dataset's "Schema" tab on the UKPN portal before finalizing
# for your report - this is inferred from magnitude, not confirmed from documentation.
ENERGY_UNIT_DIVISOR = 1000  # Wh -> kWh

NOMINAL_VOLTAGE = 230.0       # UK single-phase nominal, volts
VOLTAGE_NOISE_STD = 1.5       # small realistic jitter, volts
VOLTAGE_SAG_PER_KW = 0.15     # synthetic sag: higher load -> slightly lower voltage
ASSUMED_POWER_FACTOR = 0.95   # used to derive current from power when not directly available

RANDOM_SEED = 42
# --------------------------------------------------------------------


def find_single_csv(directory, label):
    matches = glob.glob(os.path.join(directory, "*.csv"))
    if len(matches) == 0:
        raise FileNotFoundError(f"No CSV found in {directory} (expected the {label} export)")
    if len(matches) > 1:
        raise ValueError(f"Found {len(matches)} CSVs in {directory}, expected exactly 1: {matches}")
    print(f"Using {label}: {matches[0]}")
    return matches[0]


def main():
    np.random.seed(RANDOM_SEED)

    feeder_path = find_single_csv(LV_FEEDER_DIR, "LV Feeder consumption")

    print("\nLoading raw feeder consumption data...")
    df = pd.read_csv(feeder_path)

    required = {"lv_feeder_id", "secondary_substation_id", "total_consumption_active_import",
                "total_consumption_reactive_import", "data_collection_log_timestamp"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Raw feeder file missing expected columns: {missing}")

    if not os.path.exists(ZONE_MAP_PATH):
        raise FileNotFoundError(
            f"{ZONE_MAP_PATH} not found - run build_zone_map.py first."
        )
    zone_map = pd.read_csv(ZONE_MAP_PATH)

    print(f"Loaded {len(df)} raw readings, {len(zone_map)} feeder->zone mappings")

    # --- Join zone assignment onto every reading ---
    # IMPORTANT: join on (lv_feeder_id, secondary_substation_id) together, not lv_feeder_id
    # alone. lv_feeder_id values are reused across different substations in this dataset
    # (e.g. feeder_id 81 appears under 6 different substations) - joining on feeder_id alone
    # would silently assign readings to an arbitrary/wrong zone.
    df = df.merge(
        zone_map[["lv_feeder_id", "secondary_substation_id", "zone_id"]].drop_duplicates(
            subset=["lv_feeder_id", "secondary_substation_id"]
        ),
        on=["lv_feeder_id", "secondary_substation_id"], how="left"
    )

    unmatched = df["zone_id"].isna().sum()
    if unmatched:
        print(f"WARNING: {unmatched} readings have no zone assignment "
              f"(feeder+substation combo not present in zone map) - dropping these rows.")
        df = df.dropna(subset=["zone_id"])

    # --- Drop rows with missing consumption values before any calculation ---
    before = len(df)
    df = df.dropna(subset=["total_consumption_active_import", "total_consumption_reactive_import"])
    dropped_na = before - len(df)
    if dropped_na:
        print(f"WARNING: dropped {dropped_na} rows with missing active/reactive consumption values")

    # --- Energy -> average power (accounting for Wh -> kWh, then kWh -> kW) ---
    df["active_power"] = (
        df["total_consumption_active_import"].astype(float) / ENERGY_UNIT_DIVISOR
    ) / READING_INTERVAL_HOURS
    df["reactive_power"] = (
        df["total_consumption_reactive_import"].astype(float) / ENERGY_UNIT_DIVISOR
    ) / READING_INTERVAL_HOURS

    # --- Synthetic voltage ---
    # Nominal voltage with small random noise, plus a mild synthetic sag proportional to load
    # (higher demand -> marginally lower voltage, mimicking real feeder behaviour under load).
    noise = np.random.normal(0, VOLTAGE_NOISE_STD, size=len(df))
    sag = df["active_power"] * VOLTAGE_SAG_PER_KW
    df["voltage"] = NOMINAL_VOLTAGE - sag + noise
    df["voltage"] = df["voltage"].clip(lower=180, upper=250)  # keep within a plausible band

    # --- Synthetic current, derived from power and voltage ---
    # Single-phase approx: I = P / (V * power_factor). Power in kW -> convert to W for the calc.
    df["current"] = (df["active_power"] * 1000) / (df["voltage"] * ASSUMED_POWER_FACTOR)

    # --- Placeholder anomaly columns (populated by the injection script later) ---
    df["is_injected_anomaly"] = False
    df["anomaly_type"] = pd.Series([None] * len(df), dtype="object")  # explicit object dtype,
    # not float64, so string values (e.g. "voltage_dip") can be assigned into it later
    # without pandas raising a dtype-casting error

    # --- Final tidy-up ---
    df = df.rename(columns={"data_collection_log_timestamp": "timestamp", "lv_feeder_id": "feeder_id"})
    out_cols = ["timestamp", "feeder_id", "zone_id", "active_power", "voltage",
                "current", "reactive_power", "is_injected_anomaly", "anomaly_type"]
    df = df[out_cols].sort_values("timestamp").reset_index(drop=True)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nWrote {len(df)} rows to {OUTPUT_PATH}")
    print(f"Feeders: {df['feeder_id'].nunique()} | Zones: {df['zone_id'].nunique()}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"\nSample rows:")
    print(df.head(5).to_string())
    print(f"\nActive power stats (kW):\n{df['active_power'].describe()}")
    print(f"\nVoltage stats (V):\n{df['voltage'].describe()}")


if __name__ == "__main__":
    main()