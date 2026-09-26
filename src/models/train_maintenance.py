import os
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ETT_DIR = os.path.join(BASE_DIR, "..", "..", "data", "raw", "ett")
DATA_ROOT = os.path.join(BASE_DIR, "..", "..", "data")
ZONE_MAP_PATH = os.path.join(DATA_ROOT, "processed", "feeder_zone_map.csv")
MODELS_DIR = os.path.join(BASE_DIR, "maintenance")

RISK_PERCENTILE = 0.90  # top 10% of a transformer's OWN oil temp readings = "high risk"
ROLL_WINDOW = 6         # captures sustained loading, not just an instantaneous spike -
                         # oil temperature rises with thermal lag, so a rolling load
                         # signal is more physically meaningful than instant load alone

# --- SYNTHETIC transformer -> substation/zone assignment (DOCUMENTED MODELING ASSUMPTION) ---
# The ETT dataset (T1/T2) has NO real location data at all - it's a public benchmark
# with no facility/geo fields. With only 2 transformers, a deliberate assignment
# (rather than a random draw) is the more honest and more useful choice: T1 is placed
# at the Hospital substation and T2 at the Industrial substation, chosen from the real
# feeder_zone_map.csv output, to give a meaningful contrast in criticality tier for
# the demo/report. This is NOT real telemetry location - say so explicitly in your report.
TRANSFORMER_ZONE_ASSIGNMENT = {
    "T1": "SPN-R000000730610-000-032Z",  # Hospital, zone Z2, Critical
    "T2": "EPN-R00000000A01C-000-023Z",  # Industrial, zone Z5, High
}


def load_transformer(path, transformer_id):
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["transformer_id"] = transformer_id
    df["avg_load"] = df[["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL"]].mean(axis=1)
    df["avg_load_roll_mean"] = df["avg_load"].rolling(ROLL_WINDOW).mean()
    df["avg_load_roll_std"] = df["avg_load"].rolling(ROLL_WINDOW).std()
    return df


def attach_zone_info(df):
    """Joins each transformer to its assigned substation's real zone/criticality
    metadata from feeder_zone_map.csv, via the deliberate TRANSFORMER_ZONE_ASSIGNMENT
    mapping above. Synthetic assignment, real zone/criticality data once assigned."""
    if not os.path.exists(ZONE_MAP_PATH):
        raise FileNotFoundError(f"{ZONE_MAP_PATH} not found - run build_zone_map.py first.")
    zone_map = pd.read_csv(ZONE_MAP_PATH)
    zone_cols = ["secondary_substation_id", "zone_id", "facility_type",
                 "criticality_tier", "latitude", "longitude"]
    zone_lookup = zone_map[zone_cols].drop_duplicates(subset="secondary_substation_id")
    zone_lookup = zone_lookup.set_index("secondary_substation_id")

    assign_df = pd.DataFrame([
        {"transformer_id": tid, "secondary_substation_id": sub_id}
        for tid, sub_id in TRANSFORMER_ZONE_ASSIGNMENT.items()
    ]).merge(zone_lookup, left_on="secondary_substation_id", right_index=True, how="left")

    missing = assign_df[assign_df["zone_id"].isna()]
    if len(missing):
        raise ValueError(
            f"Substation ID(s) in TRANSFORMER_ZONE_ASSIGNMENT not found in "
            f"feeder_zone_map.csv: {missing['secondary_substation_id'].tolist()}"
        )

    print("\nTransformer -> zone assignment (synthetic, deliberate):")
    print(assign_df.to_string(index=False))

    return df.merge(assign_df, on="transformer_id", how="left")


def main():
    print("Loading real transformer data (ETTm1 + ETTm2)...")
    paths = {
        "T1": os.path.join(ETT_DIR, "ETTm1.csv"),
        "T2": os.path.join(ETT_DIR, "ETTm2.csv"),
    }
    dfs = []
    for tid, p in paths.items():
        if not os.path.exists(p):
            print(f"WARNING: {p} not found, skipping {tid}")
            continue
        dfs.append(load_transformer(p, tid))
        print(f"  Loaded {tid}: {len(dfs[-1])} rows")

    if not dfs:
        raise FileNotFoundError("Neither ETTm1.csv nor ETTm2.csv found in data/raw/ett/")

    df = pd.concat(dfs, ignore_index=True).dropna()

    print("\nAttaching zone/criticality info (synthetic transformer->substation assignment)...")
    df = attach_zone_info(df)

    # Label: top decile of oil temperature, computed PER TRANSFORMER, not globally -
    # different transformers can run at different normal temperature bands, same
    # principle as per-feeder normalization used elsewhere in this project.
    print(f"\nLabeling top {(1 - RISK_PERCENTILE) * 100:.0f}% of oil temp per transformer as high risk...")
    df["high_risk"] = 0
    for tid, group in df.groupby("transformer_id"):
        threshold = group["OT"].quantile(RISK_PERCENTILE)
        df.loc[group.index, "high_risk"] = (group["OT"] > threshold).astype(int)
        print(f"  {tid}: OT threshold = {threshold:.2f}")

    # IMPORTANT: OT itself is NOT a feature - only load measurements are. This is
    # the fix for the leakage in the previous version, where HUFL was both a
    # feature AND part of the rule that defined the label.
    feature_cols = ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL",
                     "avg_load_roll_mean", "avg_load_roll_std"]
    X = df[feature_cols].values
    y = df["high_risk"].values

    print(f"\nHigh-risk rate: {y.mean() * 100:.1f}% ({y.sum()}/{len(y)} rows)")

    train_df, test_df = train_test_split(
        df, test_size=0.2, random_state=42, stratify=df["high_risk"]
    )
    X_train = train_df[feature_cols].values
    X_test = test_df[feature_cols].values
    y_train = train_df["high_risk"].values
    y_test = test_df["high_risk"].values

    print(f"Training RandomForestClassifier on {X_train.shape[0]} samples...")
    clf = RandomForestClassifier(
        n_estimators=100, max_depth=10, random_state=42, class_weight="balanced"
    )
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, preds, target_names=["Low Risk", "High Risk"]))

    # --- Reference stats for the diagnosis layer (maintenance_diagnosis.py) ---
    # Computed on TRAINING data only, per transformer - lets the diagnosis layer
    # tell a genuinely abnormal reading apart from that transformer's normal range,
    # without needing labeled fault-type data (which doesn't exist anywhere here).
    print("\nComputing per-transformer reference stats for diagnosis layer...")
    eps = 1e-6
    train_df = train_df.copy()
    hv_total = train_df["HUFL"] + train_df["HULL"]
    lv_total = train_df["LUFL"] + train_df["LULL"]
    train_df["hv_lv_skew"] = (hv_total - lv_total) / (hv_total + lv_total + eps)

    def robust_stats(series):
        """Median + MAD (median absolute deviation) instead of mean/std. ETT's
        HUFL/HULL/LUFL/LULL features can be negative, so hv_total+lv_total can
        cross exactly through zero from cancellation - any ratio/skew built on
        them gets occasional extreme outliers that blow up mean/std (seen: a
        std of 275,293 on a value mathematically bounded to [-1, 1]). Median/MAD
        barely move under that kind of outlier, which is the whole point."""
        median = float(series.median())
        mad = float((series - median).abs().median())
        return median, (1.4826 * mad + eps)  # 1.4826 scales MAD to be ~std-comparable
                                               # for a normal distribution

    ref_stats = {}
    for tid, group in train_df.groupby("transformer_id"):
        rm_med, rm_scale = robust_stats(group["avg_load_roll_mean"])
        rs_med, rs_scale = robust_stats(group["avg_load_roll_std"])
        sk_med, sk_scale = robust_stats(group["hv_lv_skew"])
        ref_stats[tid] = {
            "roll_mean_median": rm_med, "roll_mean_scale": rm_scale,
            "roll_std_median": rs_med, "roll_std_scale": rs_scale,
            "hv_lv_skew_median": sk_med, "hv_lv_skew_scale": sk_scale,
        }
    print(json.dumps(ref_stats, indent=2))

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "rf_maintenance.pkl")
    config_path = os.path.join(MODELS_DIR, "maintenance_config.json")

    joblib.dump(clf, model_path)
    with open(config_path, "w") as f:
        json.dump({
            "feature_cols": feature_cols,
            "risk_percentile": RISK_PERCENTILE,
            "roll_window": ROLL_WINDOW,
            "transformer_zone_assignment": TRANSFORMER_ZONE_ASSIGNMENT,
            "diagnosis_reference_stats": ref_stats,
        }, f, indent=2)

    print(f"\nModel saved to {model_path}")
    print(f"Config saved to {config_path}")

    # Save a real held-out sample (mix of low and high risk rows across both
    # transformers) for /equipment and /maintenance to serve genuine inference
    # on, honestly labeled as historical ETT data, not live sensor readings.
    # Now includes zone_id/facility_type/criticality_tier so the UI/API can show
    # WHERE each transformer is and how urgently a flagged risk should be treated.
    sample_path = os.path.join(MODELS_DIR, "maintenance_sample.csv")
    low_risk_sample = test_df[test_df["high_risk"] == 0].sample(n=30, random_state=42)
    high_risk_sample = test_df[test_df["high_risk"] == 1].sample(
        n=min(20, (test_df["high_risk"] == 1).sum()), random_state=42
    )
    sample_df = pd.concat([low_risk_sample, high_risk_sample]).sample(frac=1, random_state=42)
    sample_cols = feature_cols + ["transformer_id", "date", "OT", "high_risk",
                                   "zone_id", "facility_type", "criticality_tier",
                                   "latitude", "longitude"]
    sample_df[sample_cols].to_csv(sample_path, index=False)
    print(f"Serving sample ({len(sample_df)} real rows) saved to {sample_path}")


if __name__ == "__main__":
    main()