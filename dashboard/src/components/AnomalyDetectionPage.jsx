import { useState, useEffect } from 'react';
import axios from 'axios';
import MetricCard from '../components/MetricCard';
 
const API = 'http://localhost:8000';
 
export default function AnomalyDetectionPage() {
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState([]);
  const [error, setError] = useState(null);
 
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, queueRes] = await Promise.all([
          axios.get(`${API}/anomalies/stats`),
          axios.get(`${API}/anomalies/queue`)
        ]);
        setStats(statsRes.data);
        setQueue(queueRes.data);
        setError(null);
      } catch (err) {
        setError('Could not reach the API.');
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);
 
  if (error) return <div className="error-state">{error}</div>;
 
  return (
    <div className="page">
      <h1>Anomaly Detection</h1>
      <p>Isolation forest · voltage-deviation severity heuristic</p>
 
      <div className="metrics-grid">
        <MetricCard label="Open anomalies" value={stats?.open_count ?? '--'} />
        <MetricCard label="Critical (unresolved)" value={stats?.critical_unresolved ?? '--'} />
        <MetricCard
          label="Mean time to detect"
          value={stats?.mean_time_to_detect_sec ?? '--'}
          unit="s"
        />
        <MetricCard
          label="Flagged rate"
          value={stats?.false_positive_rate ?? '--'}
          unit="%"
          delta="Precision is currently low (~4%) - most flagged entries are false positives, not confirmed anomalies"
          deltaType="warn"
        />
      </div>
 
      <div className="card">
        <h3>Anomaly queue</h3>
        {queue.length === 0 ? (
          <p>No anomalies currently flagged.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Asset</th>
                <th>Zone</th>
                <th>Severity</th>
                <th>Timestamp</th>
                <th>Voltage</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((a) => (
                <tr key={a.id}>
                  <td>{a.id}</td>
                  <td>{a.type}</td>
                  <td>{a.asset}</td>
                  <td>{a.zone}</td>
                  <td className={`severity-${a.severity.toLowerCase()}`}>{a.severity}</td>
                  <td>{new Date(a.timestamp).toLocaleString()}</td>
                  <td>{a.voltage} V</td>
                  <td>{a.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
 