"""
build_zone_map.py

Builds data/processed/feeder_zone_map.csv by:
  1. Extracting distinct substations directly from the LV Feeder consumption file
     (using its embedded substation_geo_location - no risky join needed for this part)
  2. Clustering those substations into 12 geographic zones (k-means on lat/long)
  3. Best-effort enrichment from the Secondary Sites file (customer count, ONAN rating)
     by matching secondary_substation_id <-> functionallocation. This step is optional -
     if the match rate is low, the script warns you but still produces a usable output.

Expected location: src/etl/build_zone_map.py
Auto-detects the CSV files in data/raw/ukpn_feeders/ and data/raw/topology_source/
so you don't need to rename anything - just make sure only one CSV sits in each folder.
"""

import os
import re
import glob
import argparse
import pandas as pd
from sklearn.cluster import KMeans

# ---- CONFIG ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(SCRIPT_DIR, "..", "..", "data")

LV_FEEDER_DIR = os.path.join(DATA_ROOT, "raw", "ukpn_feeders")
SECONDARY_SITES_DIR = os.path.join(DATA_ROOT, "raw", "topology_source")
OUTPUT_PATH = os.path.join(DATA_ROOT, "processed", "feeder_zone_map.csv")

N_ZONES = 5  # Reduced from 12: only 15 distinct substations in the LV Feeder export,
             # so 12 zones would force near-arbitrary 1-2 substation clusters.
             # 5 zones gives ~3 substations/zone on average - a more honest grouping.
             # Override via command line: python build_zone_map.py --zones 4
# --------------------------------------------------------------------


def find_single_csv(directory, label):
    """Finds the one CSV file in a directory. Errors clearly if 0 or 2+ are found."""
    matches = glob.glob(os.path.join(directory, "*.csv"))
    if len(matches) == 0:
        raise FileNotFoundError(f"No CSV found in {directory} (expected the {label} export)")
    if len(matches) > 1:
        raise ValueError(
            f"Found {len(matches)} CSVs in {directory}, expected exactly 1 (the {label} export): "
            f"{matches}. Move extras elsewhere or set the path explicitly."
        )
    print(f"Using {label}: {matches[0]}")
    return matches[0]


def parse_geopoint(value):
    """
    Opendatasoft geopoint exports usually come as "lat, lon" strings.
    Returns (lat, lon) as floats, or (None, None) if unparseable.
    """
    if pd.isna(value):
        return None, None
    match = re.findall(r"-?\d+\.?\d*", str(value))
    if len(match) >= 2:
        return float(match[0]), float(match[1])
    return None, None


def main():
    parser = argparse.ArgumentParser(description="Build feeder-to-zone mapping")
    parser.add_argument("--zones", type=int, default=N_ZONES,
                         help=f"Number of zones to cluster substations into (default: {N_ZONES})")
    args = parser.parse_args()
    n_zones = args.zones

    lv_feeder_path = find_single_csv(LV_FEEDER_DIR, "LV Feeder consumption")
    secondary_sites_path = find_single_csv(SECONDARY_SITES_DIR, "Secondary Sites")

    print(f"\nLoading LV feeder data...")
    feeders = pd.read_csv(lv_feeder_path)

    required_cols = {"lv_feeder_id", "secondary_substation_id", "substation_geo_location"}
    missing = required_cols - set(feeders.columns)
    if missing:
        raise ValueError(
            f"LV feeder file is missing expected columns: {missing}. "
            f"Found columns: {list(feeders.columns)}"
        )

    # Distinct substations (a substation may serve multiple feeders)
    substations = feeders[["secondary_substation_id", "substation_geo_location"]].drop_duplicates()
    substations[["latitude", "longitude"]] = substations["substation_geo_location"].apply(
        lambda v: pd.Series(parse_geopoint(v))
    )

    before = len(substations)
    substations = substations.dropna(subset=["latitude", "longitude"])
    dropped = before - len(substations)
    if dropped:
        print(f"WARNING: dropped {dropped} substations with unparseable coordinates "
              f"(check substation_geo_location format if this seems high)")

    print(f"Found {len(substations)} distinct substations with valid coordinates")

    if len(substations) < n_zones:
        raise ValueError(
            f"Only {len(substations)} distinct substations found, but --zones={n_zones}. "
            f"Reduce --zones or pull more feeders."
        )

    # --- Cluster into zones ---
    kmeans = KMeans(n_clusters=n_zones, random_state=42, n_init=10)
    substations["zone_cluster"] = kmeans.fit_predict(substations[["latitude", "longitude"]])
    substations["zone_id"] = substations["zone_cluster"].apply(lambda c: f"Z{c + 1}")

    zone_counts = substations["zone_id"].value_counts().sort_index()
    print("\nSubstations per zone:")
    print(zone_counts.to_string())

    # --- Best-effort enrichment from Secondary Sites ---
    enrichment_cols = []
    if os.path.exists(secondary_sites_path):
        print(f"\nAttempting enrichment from Secondary Sites...")
        sec_sites = pd.read_csv(secondary_sites_path)

        if "functionallocation" in sec_sites.columns:
            match_ids = set(substations["secondary_substation_id"]) & set(sec_sites["functionallocation"])
            match_rate = len(match_ids) / len(substations) * 100
            print(f"ID match rate against Secondary Sites: {match_rate:.1f}% "
                  f"({len(match_ids)}/{len(substations)} substations matched)")

            if match_rate > 10:  # worth keeping even a partial match
                keep_cols = [c for c in ["functionallocation", "CustomerCount", "onanrating",
                                          "indooroutdoor", "substationalias"] if c in sec_sites.columns]
                enrichment = sec_sites[keep_cols].drop_duplicates(subset="functionallocation")
                substations = substations.merge(
                    enrichment, left_on="secondary_substation_id",
                    right_on="functionallocation", how="left"
                )
                enrichment_cols = [c for c in keep_cols if c != "functionallocation"]
            else:
                print("Match rate too low to be useful - skipping enrichment. "
                      "Zone map will still work fine without it.")
        else:
            print("Secondary Sites file missing 'functionallocation' column - skipping enrichment.")
    else:
        print(f"\nSecondary Sites file not found - skipping enrichment "
              f"(this is fine, zone map doesn't depend on it).")

    # --- Join zone_id back onto every feeder (not just distinct substations) ---
    zone_map = feeders[["lv_feeder_id", "secondary_substation_id"]].drop_duplicates().merge(
        substations[["secondary_substation_id", "latitude", "longitude", "zone_id"] + enrichment_cols],
        on="secondary_substation_id", how="left"
    )

    unmapped = zone_map["zone_id"].isna().sum()
    if unmapped:
        print(f"\nWARNING: {unmapped} feeders could not be assigned a zone "
              f"(likely coordinate parsing issues) - check these rows before proceeding.")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    zone_map.to_csv(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(zone_map)} feeder->zone mappings to {OUTPUT_PATH}")
    print(zone_map.head(10).to_string())


if __name__ == "__main__":
    main()