export default function AnomalyDetectionPage() {
  return (
    <div className="page">
      <h2>Anomaly Detection</h2>
      <p>Isolation forest + residual thresholding · 30-day window</p>
      <div className="card">
        <p>📊 Anomaly stats and queue will appear here.</p>
        <p>(Connect to /anomalies/stats and /anomalies/queue endpoints)</p>
      </div>
    </div>
  );
}