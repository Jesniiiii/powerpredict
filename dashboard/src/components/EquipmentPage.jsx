const equipment = [
  { id: 'T-14', name: 'Transformer T-14', zone: 'Zone 4', health: 62, status: 'bad', lastCheck: '2 days ago' },
  { id: 'T-08', name: 'Transformer T-08', zone: 'Zone 3', health: 78, status: 'mid', lastCheck: '5 days ago' },
  { id: 'F-3', name: 'Feeder switch F-3', zone: 'Zone 4', health: 96, status: 'good', lastCheck: '1 day ago' },
  { id: 'S-11', name: 'Substation relay S-11', zone: 'Zone 2', health: 89, status: 'good', lastCheck: '3 days ago' },
];

export default function EquipmentPage() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Equipment health</span>
        <span className="panel-tag">{equipment.length} UNITS</span>
      </div>
      <table className="equip-table">
        <thead>
          <tr>
            <th>Unit</th>
            <th>Zone</th>
            <th>Health</th>
            <th>Last checked</th>
          </tr>
        </thead>
        <tbody>
          {equipment.map(e => (
            <tr key={e.id}>
              <td>{e.name}</td>
              <td>{e.zone}</td>
              <td><span className={`health-pill ${e.status}`}>{e.health}%</span></td>
              <td>{e.lastCheck}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}