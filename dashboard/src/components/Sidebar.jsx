export default function Sidebar({ currentPage, onNavigate }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'equipment', label: 'Equipment' },
    { id: 'alerts', label: 'Alert history' },
    { id: 'settings', label: 'Settings' },
  ];

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

      {navItems.map(item => (
        <div
          key={item.id}
          className={`nav-item ${currentPage === item.id ? 'active' : ''}`}
          onClick={() => onNavigate(item.id)}
        >
          {item.label}
        </div>
      ))}
    </div>
  );
}