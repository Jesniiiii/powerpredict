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
      // Format horizon data for chart
      if (res.data.accuracy_by_horizon) {
        const data = Object.entries(res.data.accuracy_by_horizon).map(([k, v]) => ({
          horizon: k,
          accuracy: v
        }));
        setHorizonData(data);
      }
    };
    fetchMetrics();
  }, []);useEffect(() => {
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

  fetchMetrics();                                  // fetch immediately on mount
  const interval = setInterval(fetchMetrics, 10000); // then refetch every 10s
  return () => clearInterval(interval);              // cleanup on unmount
}, []);

  return (
    <div className="page forecasting">
      <h1>Load Forecasting</h1>
      <div className="metrics-grid">
        <MetricCard label="MAPE (24h)" value={metrics.mape_24h?.toFixed(1) || '--'} unit="%" />
        <MetricCard label="R² Score" value={metrics.r2_score?.toFixed(3) || '--'} />
        <MetricCard label="Peak Forecast" value={metrics.peak_forecast?.toFixed(1) || '--'} unit="kW" />
        <MetricCard label="Model Drift" value={metrics.model_drift?.toFixed(1) || '--'} unit="%" />
      </div>
      <div className="card">
        <h3>Accuracy by Horizon</h3>
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
        <ul>
          {Object.entries(metrics.feature_importance || {}).map(([key, value]) => (
            <li key={key}>{key}: {value}%</li>
          ))}
        </ul>
      </div>
    </div>
  );
}