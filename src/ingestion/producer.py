import json
import time
import os
import argparse
import pandas as pd
from kafka import KafkaProducer


def main():
    parser = argparse.ArgumentParser(description="PowerPredict replay producer")
    parser.add_argument(
        "--speed", type=float, default=150.0,
        help="Compression factor: real seconds of source data per 1 real second of replay. "
             "E.g. --speed 150 turns a 5-min (300s) reading gap into ~2 real seconds between messages. "
             "Lower = slower/more realistic, higher = faster demo."
    )
    parser.add_argument(
        "--loop", action="store_true", default=True,
        help="Loop back to the start when the stream ends (default: on)."
    )
    parser.add_argument("--no-loop", dest="loop", action="store_false")
    args = parser.parse_args()

    producer = KafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "..", "..", "data", "processed", "feeder_stream_injected.csv")

    # Expected columns in feeder_stream.csv (built by the merge/prep script, not this one):
    #   timestamp, feeder_id, zone_id, active_power, voltage, current, reactive_power,
    #   is_injected_anomaly (bool, optional), anomaly_type (str, optional)
    df = pd.read_csv(data_path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    print(f"Loaded {len(df)} readings across {df['feeder_id'].nunique()} feeders")
    print(f"Replay speed: {args.speed}x compression | Loop: {args.loop}")

    loop_count = 0
    while True:
        loop_count += 1
        print(f"--- Starting replay loop {loop_count} ---")

        prev_ts = None
        for _, row in df.iterrows():
            if prev_ts is not None:
                real_gap_seconds = (row["timestamp"] - prev_ts).total_seconds()
                sleep_time = max(0.05, real_gap_seconds / args.speed)
                time.sleep(sleep_time)
            prev_ts = row["timestamp"]

            message = {
                "feeder_id": row["feeder_id"],
                "zone_id": row["zone_id"],
                "timestamp": str(row["timestamp"]),
                "active_power": float(row["active_power"]),
                "voltage": float(row["voltage"]),
                "current": float(row["current"]),
                "reactive_power": float(row["reactive_power"]),
                "is_injected_anomaly": bool(row["is_injected_anomaly"]) if "is_injected_anomaly" in row and pd.notna(row["is_injected_anomaly"]) else False,
                "anomaly_type": row["anomaly_type"] if "anomaly_type" in row and pd.notna(row["anomaly_type"]) else None,
            }
            producer.send("grid-readings", value=message)
            print(f"Sent [{message['feeder_id']} / {message['zone_id']}]: "
                  f"P={message['active_power']:.2f} V={message['voltage']:.1f}")

        if not args.loop:
            break

    print("Stream finished")


if __name__ == "__main__":
    main()