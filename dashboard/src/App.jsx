import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Dashboard from './components/Dashboard';
import LoginPage from './components/LoginPage';
import Sidebar from './components/Sidebar';
import ThemeToggle from './components/ThemeToggle';
import AlertBell from './components/AlertBell';
import EquipmentPage from './components/EquipmentPage';
import AlertHistoryPage from './components/AlertHistoryPage';
import SettingsPage from './components/SettingsPage';
import LiveMonitoring from './components/LiveMonitoring';
import ForecastingPage from './components/ForecastingPage';
import AnomalyDetectionPage from './components/AnomalyDetectionPage';
import ReportsPage from './components/ReportsPage';
import './App.css';

const API = 'http://localhost:8000';

const ALLOWED_PAGES = {
  admin: ['dashboard', 'monitoring', 'forecasting', 'anomalies', 'equipment', 'reports', 'settings'],
  engineer: ['dashboard', 'monitoring', 'forecasting', 'anomalies', 'equipment'],
  viewer: ['dashboard', 'monitoring', 'anomalies', 'equipment'],
};

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [role, setRole] = useState(null);
  const [fullName, setFullName] = useState(null);
  const [page, setPage] = useState('dashboard');
  const [theme, setTheme] = useState('light');
  const [checkingSession, setCheckingSession] = useState(true);

  // Restore session on page load
  useEffect(() => {
    const token = localStorage.getItem('pp_token');
    if (!token) {
      setCheckingSession(false);
      return;
    }
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    axios.get(`${API}/auth/me`)
      .then(res => {
        setRole(res.data.role);
        setFullName(res.data.full_name);
        setLoggedIn(true);
        setPage((ALLOWED_PAGES[res.data.role] || ALLOWED_PAGES.viewer)[0]);
      })
      .catch(() => {
        localStorage.removeItem('pp_token');
        delete axios.defaults.headers.common['Authorization'];
      })
      .finally(() => setCheckingSession(false));
  }, []);

  function handleLogin(token, userRole, userFullName, keepSignedIn) {
    if (keepSignedIn) {
      localStorage.setItem('pp_token', token);
    }
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    setRole(userRole);
    setFullName(userFullName);
    setLoggedIn(true);
    setPage((ALLOWED_PAGES[userRole] || ALLOWED_PAGES.viewer)[0]);
  }

  function handleLogout() {
    localStorage.removeItem('pp_token');
    delete axios.defaults.headers.common['Authorization'];
    setLoggedIn(false);
    setRole(null);
    setFullName(null);
  }

  function toggleTheme() {
    setTheme(t => (t === 'light' ? 'dark' : 'light'));
  }

  const allowedForRole = ALLOWED_PAGES[role] || ALLOWED_PAGES.viewer;

  useEffect(() => {
    if (role && !allowedForRole.includes(page)) {
      setPage(allowedForRole[0]);
    }
  }, [role, page]);

  if (checkingSession) {
    return <div data-theme={theme} className="loading-state">Checking session...</div>;
  }

  if (!loggedIn) {
    return (
      <div data-theme={theme}>
        <LoginPage onLogin={handleLogin} />
      </div>
    );
  }

  const pageTitles = {
    dashboard: ['Grid Operations Dashboard', 'Live grid overview — 5 zones'],
    monitoring: ['Live Monitoring', 'Streaming telemetry · InfluxDB'],
    forecasting: ['Load Forecasting', ''],
    anomalies: ['Anomaly Detection', 'Autoencoder reconstruction · voltage-deviation severity heuristic'],
    equipment: ['Equipment Health', 'Random Forest + rule-based repair diagnosis'],
    reports: ['Reports', ''],
    settings: ['Settings', ''],
  };

  const initials = (fullName || role || '??').slice(0, 2).toUpperCase();

  return (
    <div data-theme={theme} className="app-layout">
      <Sidebar currentPage={page} onNavigate={setPage} onLogout={handleLogout} role={role} allowedPages={allowedForRole} />
      <div className="main-area">
        <header className="topbar">
          <div>
            <div className="topbar-title">{pageTitles[page][0]}</div>
            {pageTitles[page][1] && <div className="topbar-sub">{pageTitles[page][1]}</div>}
          </div>
          <div className="topbar-right">
            <AlertBell />
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <span className="role-badge">{(role || '').toUpperCase()}</span>
            <div className="avatar">{initials}</div>
          </div>
        </header>
        <main className="content">
          {page === 'dashboard' && <Dashboard />}
          {page === 'monitoring' && <LiveMonitoring />}
          {page === 'forecasting' && <ForecastingPage />}
          {page === 'anomalies' && <AnomalyDetectionPage />}
          {page === 'equipment' && <EquipmentPage />}
          {page === 'reports' && <ReportsPage />}
          {page === 'settings' && <SettingsPage />}
        </main>
      </div>
    </div>
  );
}

export default App;