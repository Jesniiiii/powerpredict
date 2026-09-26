import { useState } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';

function downloadCSV(filename, rows) {
  if (!rows || rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const csv = [
    headers.join(','),
    ...rows.map(row => headers.map(h => JSON.stringify(row[h] ?? '')).join(','))
  ].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const [reliability, setReliability] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [anomalyLog, setAnomalyLog] = useState(null);
  const [loading, setLoading] = useState(null);
  const [error, setError] = useState(null);

  async function generate(type) {
    setLoading(type);
    setError(null);
    try {
      if (type === 'reliability') {
        const res = await axios.get(`${API}/reports/reliability`);
        setReliability(res.data);
      } else if (type === 'backtest') {
        const res = await axios.get(`${API}/reports/forecast-backtest`);
        setBacktest(res.data);
      } else if (type === 'anomaly') {
        const res = await axios.get(`${API}/reports/anomaly-log`);
        setAnomalyLog(res.data);
      }
    } catch {
      setError(`Could not generate the ${type} report.`);
    }
    setLoading(null);
  }

  return (
    <div className="page">
      <h1>Reports</h1>
      {error && <div className="notice-banner warn">{error}</div>}

      <div className="reports-grid">
        {/* Reliability report */}
        <div className="card">
          <h3>Reliability & Incident Summary</h3>
          <button className="btn-primary" onClick={() => generate('reliability')} disabled={loading === 'reliability'} style={{ marginTop: 14 }}>
            {loading === 'reliability' ? 'Generating...' : 'Generate report'}
          </button>
          {reliability && (
            <div style={{ marginTop: 16 }}>
              <p><strong>Total incidents:</strong> {reliability.total_incidents}</p>
              <p><strong>Unplanned:</strong> {reliability.unplanned_incidents} &nbsp; <strong>Planned:</strong> {reliability.planned_incidents}</p>
              <p><strong>Customers affected:</strong> {reliability.customers_affected}</p>
              <p><strong>By category:</strong></p>
              <ul>
                {Object.entries(reliability.incidents_by_category || {}).map(([k, v]) => (
                  <li key={k}>{k}: {v}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Forecast backtest */}
        <div className="card">
          <h3>Forecast Performance Backtest</h3>
          <button className="btn-primary" onClick={() => generate('backtest')} disabled={loading === 'backtest'} style={{ marginTop: 14 }}>
            {loading === 'backtest' ? 'Generating...' : 'Generate report'}
          </button>
          {backtest && (
            <div style={{ marginTop: 16 }}>
              <p><strong>MAPE:</strong> {backtest.mape_24h?.toFixed(1)}%</p>
              <p><strong>R²:</strong> {backtest.r2_score?.toFixed(3)}</p>
              <p><strong>Peak forecast:</strong> {backtest.peak_forecast?.toFixed(1)} kW</p>
              <p><strong>Feeder:</strong> {backtest.feeder_id}</p>
            </div>
          )}
        </div>

        {/* Anomaly incident log */}
        <div className="card">
          <h3>Anomaly Incident Log</h3>
          <button className="btn-primary" onClick={() => generate('anomaly')} disabled={loading === 'anomaly'} style={{ marginTop: 14 }}>
            {loading === 'anomaly' ? 'Generating...' : 'Generate report'}
          </button>
          {anomalyLog && (
            <div style={{ marginTop: 16 }}>
              <p><strong>{anomalyLog.entries.length}</strong> entries as of {new Date(anomalyLog.generated_at).toLocaleString()}</p>
              {anomalyLog.entries.length > 0 && (
                <button
                  className="btn-sso"
                  onClick={() => downloadCSV('anomaly_log.csv', anomalyLog.entries)}
                >
                  Download as CSV
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}