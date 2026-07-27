export default function MetricCard({ label, value, unit, delta, deltaType }) {
  return (
    <div className="card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {value} <span className="unit">{unit}</span>
      </div>
      {delta && <div className={`metric-delta ${deltaType}`}>{delta}</div>}
    </div>
  );
}