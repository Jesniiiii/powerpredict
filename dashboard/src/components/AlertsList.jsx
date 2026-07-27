export default function AlertsList({ anomalies }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Anomaly alerts</span>
        <span className="panel-tag">{anomalies.length} ACTIVE</span>
      </div>
      {anomalies.length === 0 ? (
        <p className="empty-state">No anomalies detected in recent readings.</p>
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