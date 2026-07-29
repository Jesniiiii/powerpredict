import { useState, useEffect } from 'react';
import axios from 'axios';

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
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Equipment health</span>
        <span className="panel-tag">{equipment.length} UNITS · XGBOOST</span>
      </div>
      <table className="equip-table">
        <thead><tr><th>Unit</th><th>Zone</th><th>Health</th></tr></thead>
        <tbody>
          {equipment.map((e, i) => (
            <tr key={i}>
              <td>{e.name}</td>
              <td>{e.zone}</td>
              <td><span className={`health-pill ${e.status}`}>{e.health}%</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}