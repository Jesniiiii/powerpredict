import { useState, useEffect } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';

export default function SettingsPage() {
  const [settings, setSettings] = useState(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${API}/settings`)
      .then(res => setSettings(res.data))
      .catch(() => setError('Could not load settings from the API.'));
  }, []);

  async function handleSave() {
    try {
      await axios.post(`${API}/settings`, settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError('Could not save settings.');
    }
  }

  if (error) return <div className="error-state">{error}</div>;
  if (!settings) return <div className="loading-state">Loading settings...</div>;

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
          value={settings.min_voltage_threshold}
          onChange={e => setSettings({ ...settings, min_voltage_threshold: Number(e.target.value) })}
        /> V
      </div>

      <div className="settings-row">
        <div>
          <div className="settings-label">Warning threshold</div>
          <div className="settings-desc">% deviation from nominal (230V) that triggers WARNING</div>
        </div>
        <input
          className="settings-input"
          type="number"
          step="0.1"
          value={settings.voltage_warning_pct}
          onChange={e => setSettings({ ...settings, voltage_warning_pct: Number(e.target.value) })}
        /> %
      </div>

      <div className="settings-row">
        <div>
          <div className="settings-label">Critical threshold</div>
          <div className="settings-desc">% deviation from nominal (230V) that triggers CRITICAL</div>
        </div>
        <input
          className="settings-input"
          type="number"
          step="0.1"
          value={settings.voltage_critical_pct}
          onChange={e => setSettings({ ...settings, voltage_critical_pct: Number(e.target.value) })}
        /> %
      </div>

      <button className="btn-primary" onClick={handleSave} style={{ marginTop: 16 }}>
        Save settings
      </button>
      {saved && <span style={{ marginLeft: 12, color: '#3fcf6e' }}>✓ Saved</span>}
    </div>
  );
}