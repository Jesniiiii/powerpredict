import pandas as pd
df = pd.read_csv("data/processed/feeder_stream.csv", parse_dates=["timestamp"])
sample_feeder = df["feeder_uid"].iloc[0]
sub = df[df["feeder_uid"] == sample_feeder].sort_values("timestamp")

print("Total rows for this feeder:", len(sub))
print("Unique timestamps:", sub["timestamp"].nunique())
print(sub["timestamp"].diff().value_counts().head(10))