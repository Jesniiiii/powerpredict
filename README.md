# PowerPredict

**AI-driven smart predictive energy analytics platform for grid operators.**

PowerPredict ingests real UK Power Networks (UKPN) open smart-meter data through a Kafka → InfluxDB pipeline, applies machine learning for load forecasting, anomaly detection, and predictive maintenance, and serves the results through a FastAPI backend and React operations dashboard.

This project was rebuilt from the ground up after an early version was found to be evaluating models against mismatched placeholder datasets (household-level consumption data standing in for feeder-level grid data). The current version runs on real, publicly available grid data end-to-end.

---

## Architecture

```
UKPN Open Data ──► ETL scripts ──► Kafka producer ──► Kafka ──► Kafka consumer ──► InfluxDB
                                                                                        │
                                                                                        ▼
                                                                              FastAPI backend
                                                                                        │
                                                                                        ▼
                                                                            React operations dashboard
```

- **Data pipeline**: Python ETL scripts build a zone-mapped, anomaly-labeled feeder telemetry stream from real UKPN data
- **Streaming**: `kafka-python` producer replays the historical stream at configurable speed, tagged by feeder and zone
- **Storage**: InfluxDB stores time-series readings; a Kafka consumer runs live ML inference on each incoming reading
- **API**: FastAPI serves forecast, anomaly, maintenance, zone, and feeder endpoints
- **Frontend**: React (Vite) dashboard — live monitoring, forecasting, anomaly detection, equipment health, reports

---

## Data sources

| Source | Used for |
|---|---|
| [UK Power Networks Open Data Portal](https://ukpowernetworks.opendatasoft.com) — Smart Meter Consumption (LV Feeder) | Real feeder-level half-hourly active/reactive energy |
| UK Power Networks — Secondary Sites | Substation topology, coordinates, transformer ratings, customer counts |
| UK Power Networks — Live Faults | Real fault/outage event feed |
| [ETDataset (ETTm1/ETTm2)](https://github.com/zhouhaoyi/ETDataset) | Real transformer load + oil temperature, for predictive maintenance |

Voltage and current are **synthetically derived** (UK nominal 230V ± realistic variation, current derived from power/voltage with an assumed power factor), since none of the above public sources include real instantaneous voltage/current telemetry at this granularity. This is documented explicitly rather than presented as measured data.

---

## Repository structure

```
powerpredict/
├── dashboard/              # React (Vite) frontend
├── data/
│   ├── raw/                 # Original downloaded datasets (not committed - see .gitignore)
│   └── processed/           # Pipeline outputs: zone map, feeder stream, injected anomalies
├── docker/
│   └── docker-compose.yml   # Kafka, InfluxDB, Postgres
├── notebooks/               # Model development notebooks
├── src/
│   ├── api/                 # FastAPI backend
│   ├── etl/                 # build_zone_map.py, build_feeder_stream.py, inject_anomalies.py
│   ├── ingestion/            # Kafka producer.py, consumer.py
│   └── models/               # Training scripts + saved model artifacts
│       ├── anomaly/
│       ├── forecasting/
│       └── maintenance/
```

---

## Running it locally

**Prerequisites**: Python 3.13, Node.js, Docker Desktop

```powershell
# 1. Start infrastructure
docker compose -f docker\docker-compose.yml up -d

# 2. Set up Python environment
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Rebuild the data pipeline (only needed once, or after re-downloading source data)
python src\etl\build_zone_map.py
python src\etl\build_feeder_stream.py
python src\etl\inject_anomalies.py

# 4. Start the streaming pipeline (separate terminals)
python src\ingestion\producer.py --speed 150
python src\ingestion\consumer.py

# 5. Start the backend
uvicorn src.api.main:app --reload

# 6. Start the frontend
cd dashboard
npm install
npm run dev
```

Then open `http://localhost:5173`.

You'll also need a `.env` file (not committed) with an InfluxDB token:
```
INFLUXDB_TOKEN=your_token_here
```

---

## Current status

**Working and evaluated on real live data:**
- Zone mapping (5 zones, clustered from real substation coordinates)
- Feeder telemetry stream (real UKPN consumption, converted to power, tagged by feeder/zone)
- Live monitoring dashboard (real per-feeder voltage, current, power factor, status)
- Zone status map (real, computed from live thresholds)
- Anomaly injection + evaluation harness (40 labeled synthetic anomaly windows: voltage dips, load spikes, sensor dropouts, slow drift)
- Anomaly queue (real Isolation Forest detections on real feeder data)

**Known limitations, tracked honestly rather than hidden:**
- **Load forecasting model** was originally trained on a mismatched household-level dataset and has not yet been retrained on real feeder data — `/forecast/metrics` currently reports this mismatch accurately (negative R²) rather than a fabricated good score. Retraining on real feeder data with matching saved scaler/window length is the next major task.
- **Anomaly detection precision is currently low** (~4%) against the synthetic evaluation harness. The evaluation methodology itself is sound (per-feeder feature engineering, labeled ground truth, per-type recall breakdown); the model/feature set needs further iteration, or a shift toward the LSTM autoencoder already trained alongside Isolation Forest.
- **Predictive maintenance** is still trained on the unrelated AI4I industrial dataset rather than the real transformer data (ETTm1/ETTm2) already integrated into the pipeline — retrain pending.
- **Reports and Settings pages** are static UI, not yet backend-connected.

This project prioritizes an honestly-documented, real data pipeline over polished-looking numbers backed by placeholder data — several of the fixes above involved *discovering and correcting* metrics that looked plausible but were computed from stale or mismatched sources.

---

## Methodology notes

- Synthesized voltage/current is documented as such throughout, not presented as measured telemetry — no public source in this pipeline includes real instantaneous voltage/current at feeder granularity.
- Anomaly detection is evaluated against a self-injected, logged ground-truth set (40 windows, ~1.24% anomaly rate), following the standard practice in the literature for domains lacking real labeled fault data.
- The feeder load forecasting methodology follows Ugwuagbo et al.'s approach to very short-term feeder load forecasting, adapted to real UKPN feeder data.
