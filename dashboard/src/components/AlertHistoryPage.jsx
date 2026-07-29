import { useState, useEffect } from 'react';
import axios from 'axios';

export default function AlertHistoryPage() {
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('http://localhost:8000/anomalies')
      .then(res => { setAnomalies(res.data.recent_anomalies); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <p className="empty-state">Loading alert history...</p>;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Alert history</span>
        <span className="panel-tag">{anomalies.length} FLAGGED</span>
      </div>
      {anomalies.length === 0 ? (
        <p className="empty-state">No anomalies in recent readings.</p>
      ) : (
        anomalies.map((a, i) => (
          <div className="alert-item" key={i}>
            <span className="alert-dot red"></span>
            <div>
              <div className="alert-title">Active power: {a.active_power.toFixed(2)} kW</div>
              <div className="alert-meta">{a.timestamp}</div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}