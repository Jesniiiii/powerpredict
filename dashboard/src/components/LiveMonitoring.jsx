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
 
  const avgPowerFactor = feeders.length
    ? (feeders.reduce((sum, f) => sum + (f.pf ?? 0), 0) / feeders.length).toFixed(2)
    : '--';
 
  const totalActivePower = feeders.length
    ? feeders.reduce((sum, f) => sum + (f.active_power ?? 0), 0).toFixed(2)
    : '--';
 
  return (
    <div className="page live-monitoring">
      <h1>Live Monitoring</h1>
      <div className="metrics-grid">
        <MetricCard
          label="Feeders Reporting"
          value={feeders.length || '--'}
          delta={feeders.length ? 'Live from InfluxDB' : 'No live data yet'}
        />
        <MetricCard
          label="Avg. Power Factor"
          value={avgPowerFactor}
          delta={feeders.length ? `Across ${feeders.length} feeders` : ''}
        />
        <MetricCard
          label="Total Active Power"
          value={totalActivePower}
          unit="kW"
          delta="Sum across all reporting feeders"
        />
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
 