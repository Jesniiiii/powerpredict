import { useState, useEffect } from 'react';
import axios from 'axios';
import MetricCard from './MetricCard';
import ForecastChart from './ForecastChart';
import AlertsList from './AlertsList';

const API_BASE = 'http://localhost:8000';

export default function Dashboard() {
  const [forecast, setForecast] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [maintenance, setMaintenance] = useState(null);
  const [forecastHistory, setForecastHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000); // refresh every 10s
    return () => clearInterval(interval);
  }, []);

  async function fetchAll() {
    try {
      const [forecastRes, anomaliesRes, maintenanceRes] = await Promise.all([
        axios.get(`${API_BASE}/forecast`),
        axios.get(`${API_BASE}/anomalies`),
        axios.get(`${API_BASE}/maintenance`)
      ]);

      setForecast(forecastRes.data);
      setAnomalies(anomaliesRes.data.recent_anomalies);
      setMaintenance(maintenanceRes.data);

      setForecastHistory(prev => {
        const next = [...prev, {
          time: new Date(forecastRes.data.timestamp).toLocaleTimeString(),
          power: forecastRes.data.predicted_active_power_5min
        }];
        return next.slice(-15); // keep last 15 points
      });

      setError(null);
      setLoading(false);
    } catch (err) {
      setError('Could not reach the API. Is the FastAPI server running?');
      setLoading(false);
    }
  }

  if (loading) return <div className="loading-state">Loading dashboard...</div>;
  if (error) return <div className="error-state">{error}</div>;

  return (
    <div className="dashboard">
      <div className="metrics-grid">
        <MetricCard
          label="Predicted load (5 min)"
          value={forecast.predicted_active_power_5min.toFixed(2)}
          unit="kW"
        />
        <MetricCard
          label="Active anomalies"
          value={anomalies.length}
          unit=""
          deltaType={anomalies.length > 0 ? 'warn' : 'up'}
          delta={anomalies.length > 0 ? 'Review needed' : 'All clear'}
        />
        <MetricCard
          label="Equipment risk"
          value={(maintenance.failure_probability * 100).toFixed(1)}
          unit="%"
          deltaType={maintenance.risk_level === 'high' ? 'warn' : 'up'}
          delta={maintenance.risk_level === 'high' ? 'High risk' : 'Low risk'}
        />
      </div>

      <div className="panels-row">
        <ForecastChart data={forecastHistory} />
        <AlertsList anomalies={anomalies} />
      </div>
    </div>
  );
}