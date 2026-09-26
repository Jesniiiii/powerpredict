import { useState, useEffect } from 'react';
import axios from 'axios';

function criticalityClass(tier) {
  const t = (tier || '').toLowerCase();
  if (t === 'critical') return 'badge-critical';
  if (t === 'high') return 'badge-high';
  if (t === 'medium') return 'badge-medium';
  return 'badge-low';
}

function faultClass(faultType) {
  if (!faultType) return 'badge-low';
  if (faultType.startsWith('Normal')) return 'badge-normal';
  if (faultType.includes('HV/LV') || faultType.includes('Overload')) return 'badge-high';
  if (faultType.includes('Volatility')) return 'badge-high';
  if (faultType.includes('Thermal')) return 'badge-medium';
  return 'badge-medium';
}

function urgencyClass(urgency) {
  if (!urgency) return 'badge-low';
  if (urgency.includes('URGENT') || urgency.includes('EMERGENCY')) return 'badge-critical';
  if (urgency.includes('3 days')) return 'badge-high';
  if (urgency.includes('1-2 weeks')) return 'badge-medium';
  return 'badge-low';
}

const FAULT_REFERENCE = [
  {
    label: 'Normal - no risk flagged',
    dot: 'good',
    desc: 'Model did not flag elevated failure risk; continue routine monitoring.'
  },
  {
    label: 'Sustained Overload',
    dot: 'high',
    desc: 'High average loading is the likely driver. Inspect cooling system, oil quality, consider capacity upgrade.'
  },
  {
    label: 'Load Volatility / Fluctuating Demand',
    dot: 'high',
    desc: 'Unstable, fluctuating load rather than high average load. Inspect tap-changer and voltage regulation.'
  },
  {
    label: 'HV/LV Side Imbalance',
    dot: 'high',
    desc: 'Unusual imbalance between HV and LV side loading. Inspect winding insulation, bushings, tap-changer alignment.'
  },
  {
    label: 'General Thermal Stress',
    dot: 'medium',
    desc: 'Flagged high-risk but no single signal is sharply abnormal. Schedule oil sampling (DGA) and thermal imaging.'
  },
];

export default function EquipmentPage() {
  const [equipment, setEquipment] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('http://localhost:8000/equipment')
      .then(res => { setEquipment(res.data.equipment); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <p className="empty-state">Loading equipment data...</p>;

  return (
    <div>
      <div className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-header">
          <span className="panel-title">Equipment health</span>
          <span className="panel-tag">{equipment.length} UNITS · RANDOM FOREST + RULE-BASED DIAGNOSIS</span>
        </div>
        <table className="equip-table equip-table-wide">
          <thead>
            <tr>
              <th style={{ width: '20%' }}>Unit</th>
              <th style={{ width: '10%' }}>Zone</th>
              <th style={{ width: '10%' }}>Criticality</th>
              <th style={{ width: '9%' }}>Health</th>
              <th style={{ width: '16%' }}>Fault Type</th>
              <th style={{ width: '25%' }}>Recommendation</th>
              <th style={{ width: '10%' }}>Urgency</th>
            </tr>
          </thead>
          <tbody>
            {equipment.map((e, i) => (
              <tr key={i}>
                <td>
                  <div style={{ fontWeight: 600 }}>{e.name}</div>
                </td>
                <td>{e.zone}</td>
                <td><span className={`badge-pill ${criticalityClass(e.criticality_tier)}`}>{e.criticality_tier}</span></td>
                <td><span className={`health-pill ${e.status}`}>{e.health}%</span></td>
                <td><span className={`badge-pill ${faultClass(e.fault_type)}`}>{e.fault_type}</span></td>
                <td className="equip-reco-cell">{e.recommendation}</td>
                <td><span className={`badge-pill ${urgencyClass(e.urgency)}`}>{e.urgency}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">Fault Category Reference</span>
        </div>
        <div className="fault-reference-grid">
          {FAULT_REFERENCE.map(item => (
            <div key={item.label} className="fault-reference-item">
              <span className={`ref-dot ${item.dot}`}></span>
              <div>
                <div className="ref-label">{item.label}</div>
                <div className="ref-desc">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}