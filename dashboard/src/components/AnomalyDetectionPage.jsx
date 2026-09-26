import { useState, useEffect } from 'react';
import axios from 'axios';
import MetricCard from '../components/MetricCard';

const API = 'http://localhost:8000';

const severityColor = {
  CRITICAL: '#d32f2f',
  WARNING: '#ed6c02',
  INFO: '#1976d2',
};

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
          delta={stats?.false_positive_rate_note}
          deltaType="warn"
        />
      </div>

      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>Anomaly queue</h3>
          <span className="panel-tag">{queue.length} ACTIVE</span>
        </div>

        {queue.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text-secondary)' }}>
            <div style={{ fontSize: '2rem', marginBottom: 8 }}>✓</div>
            <div style={{ fontWeight: 600 }}>All Clear</div>
            <div style={{ fontSize: '0.85rem' }}>No anomalies currently flagged.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
            {queue.map((a) => (
              <div
                key={a.id}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '14px 16px', borderRadius: 10, background: 'var(--bg-body)',
                  borderLeft: `4px solid ${severityColor[a.severity] || '#999'}`
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: '0.7rem', fontWeight: 700, color: severityColor[a.severity],
                      textTransform: 'uppercase'
                    }}>
                      {a.severity}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {a.zone} · {a.facility_type} · {a.asset}
                    </span>
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 2 }}>
                    {a.type}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {a.voltage} V ({a.deviation_pct}% from nominal) · {a.active_power} kW · reconstruction error {a.reconstruction_error}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 16 }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {new Date(a.timestamp).toLocaleString()}
                  </div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600 }}>{a.status}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}