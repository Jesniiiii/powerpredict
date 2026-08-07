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
  const [latest, setLatest] = useState(null);
  const [zones, setZones] = useState([]); // NEW: real zone statuses from backend
  const [forecastHistory, setForecastHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, []);

  async function fetchAll() {
    try {
      const [forecastRes, anomaliesRes, maintenanceRes, latestRes, zonesRes] = await Promise.all([
        axios.get(`${API_BASE}/forecast`),
        axios.get(`${API_BASE}/anomalies`),
        axios.get(`${API_BASE}/maintenance`),
        axios.get(`${API_BASE}/latest`),
        axios.get(`${API_BASE}/zones`) // NEW
      ]);

      setForecast(forecastRes.data);
      setAnomalies(anomaliesRes.data.recent_anomalies || []);
      setMaintenance(maintenanceRes.data);
      setLatest(latestRes.data);
      setZones(zonesRes.data.zones || zonesRes.data); // adjust to match actual response shape once confirmed

      const newTime = new Date(forecastRes.data.timestamp);
      setForecastHistory(prev => {
        const last = prev[prev.length - 1];
        if (last && new Date(last.time).getTime() === newTime.getTime()) {
          return prev;
        }
        const next = [...prev, {
          time: newTime.toLocaleTimeString(),
          power: forecastRes.data.predicted_active_power_5min
        }];
        return next.slice(-20);
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
      {/* Metrics Grid */}
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
        <MetricCard
          label="System Voltage"
          value={latest?.voltage?.toFixed(1) ?? '--'}
          unit="V"
          deltaType={latest?.voltage < 210 ? 'warn' : 'up'}
          delta={latest?.voltage < 210 ? 'Low voltage' : 'Nominal'}
        />
      </div>

      {/* Zone Status Map - now driven by real /zones data */}
      <div className="card zone-map-card">
        <div className="card-header">
          <span>Zone status map</span>
          <span className="badge">{zones.length} ZONES</span>
        </div>
        <div className="zone-grid">
          {zones.map(({ zone_id, status }) => (
            <div key={zone_id} className={`zone-cell ${status}`}>
              {zone_id}
            </div>
          ))}
        </div>
        <div className="zone-legend">
          <span><span className="dot nominal"></span> Nominal</span>
          <span><span className="dot watch"></span> Watch</span>
          <span><span className="dot critical"></span> Critical</span>
        </div>
      </div>

      {/* Panels Row */}
      <div className="panels-row">
        <ForecastChart data={forecastHistory} />
        <AlertsList anomalies={anomalies} />
      </div>
    </div>
  );
}