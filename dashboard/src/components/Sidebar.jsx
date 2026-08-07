export default function Sidebar({ currentPage, onNavigate, onLogout, role }) {
  const navConfig = {
    Operator: ['dashboard', 'monitoring', 'forecasting', 'anomalies', 'equipment'],
    Admin: ['dashboard', 'monitoring', 'forecasting', 'anomalies', 'equipment', 'reports', 'settings'],
    Technician: ['anomalies', 'equipment'],
  };
  const visiblePages = navConfig[role] || [];

  // Helper to render icon based on page name
  const getIcon = (page) => {
    switch(page) {
      case 'dashboard': return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>;
      case 'monitoring': return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
      case 'forecasting': return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M21 12v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4"/><line x1="9" y1="16" x2="9" y2="8"/><line x1="13" y1="16" x2="13" y2="6"/><line x1="17" y1="16" x2="17" y2="10"/></svg>;
      case 'anomalies': return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>;
      case 'equipment': return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="8" x2="16" y2="8"/><line x1="8" y1="12" x2="16" y2="12"/></svg>;
      case 'reports': return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>;
      case 'settings': return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
      default: return null;
    }
  };

  // Define sections
  const monitorPages = ['dashboard', 'monitoring', 'forecasting', 'anomalies'];
  const assetPages = ['equipment', 'reports'];
  const systemPages = ['settings'];

  return (
    <div className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-seal">
          <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" width="16" height="16">
            <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/>
          </svg>
        </div>
        <div>
          <div className="sidebar-title">PowerPredict</div>
          <div className="sidebar-sub">Grid Ops Console</div>
        </div>
      </div>

      {/* Monitor section */}
      {visiblePages.some(p => monitorPages.includes(p)) && (
        <>
          <div className="nav-section-label">Monitor</div>
          {monitorPages.map(p => visiblePages.includes(p) && (
            <div
              key={p}
              className={`nav-item ${currentPage === p ? 'active' : ''}`}
              onClick={() => onNavigate(p)}
            >
              {getIcon(p)}
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </div>
          ))}
        </>
      )}

      {/* Assets section */}
      {visiblePages.some(p => assetPages.includes(p)) && (
        <>
          <div className="nav-section-label">Assets</div>
          {assetPages.map(p => visiblePages.includes(p) && (
            <div
              key={p}
              className={`nav-item ${currentPage === p ? 'active' : ''}`}
              onClick={() => onNavigate(p)}
            >
              {getIcon(p)}
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </div>
          ))}
        </>
      )}

      {/* System section */}
      {visiblePages.some(p => systemPages.includes(p)) && (
        <>
          <div className="nav-section-label">System</div>
          {systemPages.map(p => visiblePages.includes(p) && (
            <div
              key={p}
              className={`nav-item ${currentPage === p ? 'active' : ''}`}
              onClick={() => onNavigate(p)}
            >
              {getIcon(p)}
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </div>
          ))}
        </>
      )}

      <div className="sidebar-footer">
        <div className="status-row"><span className="dot on"></span> Kafka pipeline connected</div>
        <div className="status-row"><span className="dot on"></span> InfluxDB synced</div>
        <div className="nav-item" style={{ marginTop: 8 }} onClick={onLogout}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          Log out
        </div>
      </div>
    </div>
  );
}