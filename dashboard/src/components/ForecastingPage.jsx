import { useState, useEffect } from 'react';
import axios from 'axios';
import MetricCard from '../components/MetricCard';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend, ResponsiveContainer } from 'recharts';

export default function ForecastingPage() {
  const [metrics, setMetrics] = useState({});
  const [series, setSeries] = useState([]);

  useEffect(() => {
    const fetchMetrics = async () => {
      const res = await axios.get('http://localhost:8000/forecast/metrics');
      setMetrics(res.data);
      if (res.data.series) {
        setSeries(res.data.series.map(pt => ({
          time: new Date(pt.timestamp).toLocaleTimeString(),
          actual: pt.actual,
          predicted: pt.predicted
        })));
      }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="page forecasting">
      <div className="metrics-grid">
        <MetricCard label="MAPE (24h)" value={metrics.mape_24h?.toFixed(1) || '--'} unit="%" />
        <MetricCard label="R² Score" value={metrics.r2_score?.toFixed(3) || '--'} />
        <MetricCard label="Peak Forecast" value={metrics.peak_forecast?.toFixed(1) || '--'} unit="kW" />
        <MetricCard label="Model Drift" value={metrics.model_drift?.toFixed(1) || '--'} unit="%" />
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Actual vs Predicted Load</span>
          <span className="panel-tag">{metrics.source === 'live_influxdb' ? 'LIVE' : 'FALLBACK'}</span>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={series} margin={{ top: 8, right: 16, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} axisLine={false} tickLine={false} width={40} />
            <Tooltip
              contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 12, color: 'var(--text)' }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="actual" stroke="#1B4B82" strokeWidth={2} dot={false} name="Actual" />
            <Line type="monotone" dataKey="predicted" stroke="#2dd4bf" strokeWidth={2} dot={false} strokeDasharray="4 3" name="Predicted (Chronos-Bolt)" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}