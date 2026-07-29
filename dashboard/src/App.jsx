import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import LoginPage from './components/LoginPage';
import Sidebar from './components/Sidebar';
import ThemeToggle from './components/ThemeToggle';
import EquipmentPage from './components/EquipmentPage';
import AlertHistoryPage from './components/AlertHistoryPage';
import SettingsPage from './components/SettingsPage';
import './App.css';

const ALLOWED_PAGES = {
  Operator: ['dashboard', 'alerts', 'equipment'],
  Admin: ['dashboard', 'alerts', 'equipment', 'settings'],
  Technician: ['alerts', 'equipment'],
};

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [role, setRole] = useState(null);
  const [page, setPage] = useState('dashboard');
  const [theme, setTheme] = useState('light');

  function handleLogin(selectedRole) {
    setRole(selectedRole);
    setLoggedIn(true);
    setPage(ALLOWED_PAGES[selectedRole][0]);
  }

  function handleLogout() {
    setLoggedIn(false);
    setRole(null);
  }

  function toggleTheme() {
    setTheme(t => (t === 'light' ? 'dark' : 'light'));
  }

  useEffect(() => {
    if (role && !ALLOWED_PAGES[role].includes(page)) {
      setPage(ALLOWED_PAGES[role][0]);
    }
  }, [role, page]);

  if (!loggedIn) {
    return (
      <div data-theme={theme}>
        <LoginPage onLogin={handleLogin} />
      </div>
    );
  }

  const pageTitles = {
    dashboard: ['Grid Operations Dashboard', 'Zone 4 — Northern Distribution Network'],
    equipment: ['Equipment Health', 'All monitored units'],
    alerts: ['Alert History', 'Past anomaly records'],
    settings: ['Settings', 'Alert threshold configuration'],
  };

  return (
    <div data-theme={theme} className="app-layout">
      <Sidebar currentPage={page} onNavigate={setPage} onLogout={handleLogout} role={role} />
      <div className="main-area">
        <header className="topbar">
          <div>
            <div className="topbar-title">{pageTitles[page][0]}</div>
            <div className="topbar-sub">{pageTitles[page][1]}</div>
          </div>
          <div className="topbar-right">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <span className="role-badge">{role.toUpperCase()}</span>
            <div className="avatar">{role.slice(0, 2).toUpperCase()}</div>
          </div>
        </header>
        <main className="content">
          {page === 'dashboard' && <Dashboard />}
          {page === 'equipment' && <EquipmentPage />}
          {page === 'alerts' && <AlertHistoryPage />}
          {page === 'settings' && <SettingsPage />}
        </main>
      </div>
    </div>
  );
}

export default App;