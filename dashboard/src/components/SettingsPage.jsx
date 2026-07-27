import { useState } from 'react';

export default function SettingsPage() {
  const [voltageThreshold, setVoltageThreshold] = useState(210);
  const [anomalyContamination, setAnomalyContamination] = useState(0.5);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Alert thresholds</span>
        <span className="panel-tag">ADMIN</span>
      </div>
      <div className="settings-row">
        <div>
          <div className="settings-label">Minimum voltage threshold</div>
          <div className="settings-desc">Flag readings below this value</div>
        </div>
        <input
          className="settings-input"
          type="number"
          value={voltageThreshold}
          onChange={e => setVoltageThreshold(e.target.value)}
        /> V
      </div>
      <div className="settings-row">
        <div>
          <div className="settings-label">Anomaly sensitivity</div>
          <div className="settings-desc">% of readings flagged as anomalous</div>
        </div>
        <input
          className="settings-input"
          type="number"
          step="0.1"
          value={anomalyContamination}
          onChange={e => setAnomalyContamination(e.target.value)}
        /> %
      </div>
    </div>
  );
}