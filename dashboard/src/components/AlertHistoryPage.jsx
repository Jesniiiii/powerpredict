import { useState } from 'react';

const history = [
  { id: 1, title: 'Meter 4471 — voltage dip', zone: 'Zone 4', time: '2 min ago', severity: 'critical' },
  { id: 2, title: 'Feeder 12 — load spike', zone: 'Zone 4', time: '14 min ago', severity: 'warning' },
  { id: 3, title: 'Meter 2098 — possible theft', zone: 'Zone 3', time: '31 min ago', severity: 'warning' },
  { id: 4, title: 'Transformer T-14 — thermal warning', zone: 'Zone 4', time: '2 hours ago', severity: 'resolved' },
];

export default function AlertHistoryPage() {
  const [filter, setFilter] = useState('all');
  const filtered = filter === 'all' ? history : history.filter(h => h.severity === filter);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Alert history</span>
        <span className="panel-tag">{filtered.length} RECORDS</span>
      </div>
      <div className="filter-row">
        {['all', 'critical', 'warning', 'resolved'].map(f => (
          <div key={f} className={`filter-chip ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </div>
        ))}
      </div>
      {filtered.map(h => (
        <div className="alert-item" key={h.id}>
          <span className={`alert-dot ${h.severity === 'critical' ? 'red' : ''}`}></span>
          <div>
            <div className="alert-title">{h.title}</div>
            <div className="alert-meta">{h.zone} · {h.time}</div>
          </div>
        </div>
      ))}
    </div>
  );
}