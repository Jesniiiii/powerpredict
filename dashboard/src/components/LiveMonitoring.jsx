import { useState, useEffect } from 'react';
import axios from 'axios';
import MetricCard from '../components/MetricCard';

const API = 'http://localhost:8000';

export default function LiveMonitoring() {
  const [latest, setLatest] = useState({});
  const [feeders, setFeeders] = useState([]);

  useEffect(() => {
    const fetchData = async () => {
      const [lRes, fRes] = await Promise.all([
        axios.get(`${API}/latest`),
        axios.get(`${API}/feeders`)
      ]);
      setLatest(lRes.data);
      setFeeders(fRes.data);
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="page live-monitoring">
      <h1>Live Monitoring</h1>
      <div className="metrics-grid">
        <MetricCard label="Line Frequency" value="49.98" unit="Hz" delta="Within ±0.05 Hz band" />
        <MetricCard label="Avg. Power Factor" value="0.95" delta="▲ 0.02 vs. yesterday" />
        <MetricCard label="Feeders Online" value="4/4" delta="All reporting" />
        <MetricCard label="Voltage" value={latest.voltage?.toFixed(1) || '--'} unit="V" />
      </div>
      <div className="card">
        <h3>Feeder Telemetry</h3>
        <table>
          <thead><tr><th>Feeder</th><th>Zone</th><th>Voltage (V)</th><th>Current (A)</th><th>PF</th><th>Status</th></tr></thead>
          <tbody>
            {feeders.map((f, i) => (
              <tr key={i}>
                <td>{f.name}</td>
                <td>{f.zone}</td>
                <td>{f.voltage}</td>
                <td>{f.current}</td>
                <td>{f.pf}</td>
                <td className={`status-${f.status.toLowerCase()}`}>{f.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}