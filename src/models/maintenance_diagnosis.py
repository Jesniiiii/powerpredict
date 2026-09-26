"""
maintenance_diagnosis.py

Turns a binary high_risk flag from rf_maintenance.pkl into an actual repair
recommendation: WHAT kind of problem the reading looks like, WHAT to inspect,
and HOW urgently, based on the zone's criticality tier.

HONEST LIMITATION (say this explicitly in your report): no dataset in this
pipeline has real labeled fault types (e.g. "confirmed winding fault",
"confirmed cooling failure"). This is a RULE-BASED heuristic layer built on
domain-reasonable signal patterns (sustained overload vs. volatile fluctuation
vs. HV/LV side imbalance), not a model trained on true fault labels. It gives a
plausible, explainable diagnosis - not a certified one.

Depends on train_maintenance.py having been run first (needs rf_maintenance.pkl,
maintenance_config.json with diagnosis_reference_stats, and maintenance_sample.csv).

Expected location: src/models/maintenance_diagnosis.py
"""

import os
import json
import joblib
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "maintenance")

MODEL_PATH = os.path.join(MODELS_DIR, "rf_maintenance.pkl")
CONFIG_PATH = os.path.join(MODELS_DIR, "maintenance_config.json")
SAMPLE_PATH = os.path.join(MODELS_DIR, "maintenance_sample.csv")
OUTPUT_PATH = os.path.join(MODELS_DIR, "maintenance_sample_diagnosed.csv")

Z_THRESHOLD = 2.0  # how many std-devs from a transformer's own normal counts as "abnormal"

URGENCY_BY_CRITICALITY = {
    "Critical": "URGENT - schedule inspection within 24 hours",
    "High": "Schedule inspection within 3 days",
    "Medium": "Schedule inspection within 1-2 weeks",
    "Low": "Include in next routine maintenance cycle",
}


def diagnose_row(row, ref_stats):
    """Returns (fault_type, recommendation) for one row already flagged high_risk.
    Picks the single most abnormal signal (largest |z-score| vs. that transformer's
    own training-data normal range) and maps it to a plausible inspection action."""
    tid = row["transformer_id"]
    stats = ref_stats[tid]
    eps = 1e-6

    z_roll_mean = (row["avg_load_roll_mean"] - stats["roll_mean_median"]) / stats["roll_mean_scale"]
    z_roll_std = (row["avg_load_roll_std"] - stats["roll_std_median"]) / stats["roll_std_scale"]

    hv_total = row["HUFL"] + row["HULL"]
    lv_total = row["LUFL"] + row["LULL"]
    hv_lv_skew = (hv_total - lv_total) / (hv_total + lv_total + eps)
    z_hvlv = (hv_lv_skew - stats["hv_lv_skew_median"]) / stats["hv_lv_skew_scale"]

    candidates = {
        "Load Volatility / Fluctuating Demand": (z_roll_std, (
            "Sustained oil-temperature risk driven by unstable, fluctuating load rather "
            "than high average load. Inspect tap-changer operation and voltage regulation; "
            "investigate source of intermittent large loads or faulty control gear."
        )),
        "Sustained Overload": (z_roll_mean, (
            "Sustained high average loading is the likely driver. Inspect cooling system "
            "(fans, radiators, oil pumps); check oil quality for thermal degradation "
            "(consider DGA test); evaluate load redistribution or capacity upgrade."
        )),
        "HV/LV Side Imbalance": (abs(z_hvlv), (
            "Unusual imbalance between high-voltage and low-voltage side loading. "
            "Inspect winding insulation and bushings on the more heavily loaded side; "
            "check for tap-changer misalignment or an unbalanced connected load."
        )),
    }

    best_type, (best_z, best_reco) = max(candidates.items(), key=lambda kv: kv[1][0])

    if best_z < Z_THRESHOLD:
        return ("General Thermal Stress", (
            "Reading is flagged high-risk but no single signal is sharply abnormal "
            "relative to this transformer's own history. Schedule routine oil sampling "
            "(DGA) and thermal imaging; monitor closely over the next cycle."
        ))
    return (best_type, best_reco)


def main():
    if not (os.path.exists(MODEL_PATH) and os.path.exists(CONFIG_PATH) and os.path.exists(SAMPLE_PATH)):
        raise FileNotFoundError(
            "Missing model/config/sample files - run train_maintenance.py first."
        )

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    ref_stats = config["diagnosis_reference_stats"]

    print(f"Loading maintenance sample from {SAMPLE_PATH}...")
    df = pd.read_csv(SAMPLE_PATH)

    high_risk = df[df["high_risk"] == 1].copy()
    print(f"Diagnosing {len(high_risk)} high-risk rows (out of {len(df)} sample rows)...")

    fault_types, recommendations, urgencies = [], [], []
    for _, row in high_risk.iterrows():
        fault_type, reco = diagnose_row(row, ref_stats)
        urgency = URGENCY_BY_CRITICALITY.get(row.get("criticality_tier", "Low"), "Schedule routine inspection")
        fault_types.append(fault_type)
        recommendations.append(reco)
        urgencies.append(urgency)

    high_risk["fault_type"] = fault_types
    high_risk["recommendation"] = recommendations
    high_risk["urgency"] = urgencies

    print("\nFault type breakdown:")
    print(high_risk["fault_type"].value_counts().to_string())

    print("\nSample diagnoses:")
    display_cols = ["transformer_id", "zone_id", "facility_type", "criticality_tier",
                     "fault_type", "urgency"]
    print(high_risk[display_cols].head(10).to_string(index=False))

    df_out = df.merge(
        high_risk[["transformer_id", "date", "fault_type", "recommendation", "urgency"]],
        on=["transformer_id", "date"], how="left"
    )
    df_out.to_csv(OUTPUT_PATH, index=False)
    print(f"\nWrote diagnosed sample to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()