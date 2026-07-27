import { useState } from 'react';
import Dashboard from './components/Dashboard';
import LoginPage from './components/LoginPage';
import './App.css';

function App() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [role, setRole] = useState(null);

  function handleLogin(selectedRole) {
    setRole(selectedRole);
    setLoggedIn(true);
  }

  if (!loggedIn) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="topbar-title">Grid Operations Dashboard</div>
          <div className="topbar-sub">Zone 4 — Northern Distribution Network</div>
        </div>
        <div className="topbar-right">
          <span className="role-badge">{role.toUpperCase()}</span>
          <div className="avatar">{role.slice(0, 2).toUpperCase()}</div>
        </div>
      </header>
      <main className="content">
        <Dashboard />
      </main>
    </div>
  );
}

export default App;