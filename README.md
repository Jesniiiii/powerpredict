# PowerPredict

**Final-year B.Tech project** — AI-driven smart grid analytics platform.

Real-time load forecasting, anomaly detection, and predictive maintenance
diagnosis for electrical distribution networks, built on real UK Power
Networks (UKPN) open feeder data.

## What it does

- **Load forecasting** — zero-shot forecasting via Amazon's Chronos-Bolt,
  benchmarked against a trained LSTM baseline (Chronos-Bolt: MAPE 15.93%,
  R² 0.9469 — beats the trained LSTM with zero feeder-specific training)
- **Anomaly detection** — LSTM autoencoder reconstruction-error scoring on
  live streamed grid readings
- **Zone criticality tiering** — feeders mapped to geographic zones and
  assigned a facility type (Hospital, Water Treatment, Industrial,
  Commercial, Residential) with a derived criticality tier, so anomalies
  and maintenance risk can be prioritized by real-world impact
- **Predictive maintenance** — a Random Forest flags high-risk transformer
  readings from real historical ETT data, paired with a rule-based
  diagnosis layer that names a likely fault type (Sustained Overload, Load
  Volatility, HV/LV Side Imbalance, General Thermal Stress) and an
  urgency level based on the zone's criticality tier
- **Live email alerts** — critical anomalies trigger an automated email
  notification
- **Role-based access** — JWT auth with three roles (admin / engineer /
  viewer), each seeing a different slice of the dashboard

## Stack

- **Backend:** FastAPI, TensorFlow/Keras, scikit-learn, MongoDB Atlas,
  InfluxDB
- **Frontend:** React (Vite), Recharts
- **Auth:** bcrypt + PyJWT
- **Data:** Real UKPN LV feeder consumption data, real ETT transformer
  data (ETTm1/ETTm2), synthetic-but-documented facility/zone assumptions
  where no real-world label exists

## Honesty notes

This project is upfront about what's real vs. modeled:
- No dataset here has real facility-type labels (hospital, water
  treatment, etc.) — zone criticality tiers are a documented, seeded
  synthetic assignment, not real infrastructure data
- The maintenance diagnosis layer is a rule-based heuristic, not a model
  trained on true labeled fault types (none exist in any available
  dataset) — it gives a plausible, explainable diagnosis, not a
  certified one
- Forecast/anomaly metrics shown in the UI are computed live from actual
  model output, not hardcoded placeholders

## Running locally

```bash
# Backend
docker compose -f docker/docker-compose.yml up -d   # Kafka, Zookeeper, InfluxDB
python src/ingestion/producer.py --speed 150
python src/ingestion/consumer.py
uvicorn src.api.main:app --reload

# Frontend
cd dashboard
npm run dev
```

Requires a `.env` file (not committed) with InfluxDB, MongoDB Atlas, JWT
secret, and SMTP credentials — see `.env.example` for the required keys.