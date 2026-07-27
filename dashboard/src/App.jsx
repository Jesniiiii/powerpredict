import Dashboard from './components/Dashboard';
import './App.css';

function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="topbar-title">Grid Operations Dashboard</div>
          <div className="topbar-sub">Zone 4 — Northern Distribution Network</div>
        </div>
        <div className="topbar-right">
          <span className="role-badge">OPERATOR</span>
          <div className="avatar">GO</div>
        </div>
      </header>
      <main className="content">
        <Dashboard />
      </main>
    </div>
  );
}

export default App;