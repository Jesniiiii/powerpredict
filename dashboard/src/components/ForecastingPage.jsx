import { useState, useEffect } from 'react';
import axios from 'axios';
import MetricCard from '../components/MetricCard';
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
 
export default function ForecastingPage() {
  const [metrics, setMetrics] = useState({});
  const [horizonData, setHorizonData] = useState([]);
 
  useEffect(() => {
    const fetchMetrics = async () => {
      const res = await axios.get('http://localhost:8000/forecast/metrics');
      setMetrics(res.data);
      if (res.data.accuracy_by_horizon) {
        const data = Object.entries(res.data.accuracy_by_horizon).map(([k, v]) => ({
          horizon: k,
          accuracy: v
        }));
        setHorizonData(data);
      }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);
 
  const modelUnreliable = metrics.r2_score !== undefined && metrics.r2_score < 0.5;
 
  return (
    <div className="page forecasting">
      <h1>Load Forecasting</h1>
 
      {modelUnreliable && (
        <div className="notice-banner warn">
          ⚠️ These metrics are evaluated live against real feeder data, but the current
          LSTM model was trained on a different (household-level) dataset and hasn't
          been retrained on real feeder data yet — the numbers below reflect that
          mismatch honestly, they aren't a display bug. A retrain on real feeder data
          is the planned next step.
        </div>
      )}
 
      <div className="metrics-grid">
        <MetricCard label="MAPE (24h)" value={metrics.mape_24h?.toFixed(1) || '--'} unit="%" />
        <MetricCard label="R² Score" value={metrics.r2_score?.toFixed(3) || '--'} />
        <MetricCard label="Peak Forecast" value={metrics.peak_forecast?.toFixed(1) || '--'} unit="kW" />
        <MetricCard label="Model Drift" value={metrics.model_drift?.toFixed(1) || '--'} unit="%" />
      </div>
 
      <div className="card">
        <h3>Accuracy by Horizon</h3>
        <p className="card-subnote">Simulated degradation curve based on the 5-min R² score above, not independently evaluated per horizon.</p>
        <BarChart width={400} height={250} data={horizonData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="horizon" />
          <YAxis />
          <Tooltip />
          <Bar dataKey="accuracy" fill="#8884d8" />
        </BarChart>
      </div>
 
      <div className="card">
        <h3>Feature Importance (SHAP)</h3>
        <p className="card-subnote">Placeholder values, not yet computed from real SHAP output.</p>
        <ul>
          {Object.entries(metrics.feature_importance || {}).map(([key, value]) => (
            <li key={key}>{key}: {value}%</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
 