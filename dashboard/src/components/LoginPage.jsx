import { useState } from 'react';

export default function LoginPage({ onLogin }) {
  const [role, setRole] = useState('Operator');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  function handleSubmit(e) {
    e.preventDefault();
    onLogin(role);
  }

  return (
    <div className="login-overlay">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <div className="login-seal">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" width="22" height="22">
              <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/>
            </svg>
          </div>
          <div className="login-title">PowerPredict</div>
          <div className="login-sub">Grid operations console</div>
        </div>

        <label className="field-label">Username</label>
        <input
          className="field-input"
          type="text"
          placeholder="operator_01"
          value={username}
          onChange={e => setUsername(e.target.value)}
        />

        <label className="field-label">Password</label>
        <input
          className="field-input"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={e => setPassword(e.target.value)}
        />

        <div className="role-tabs">
          {['Operator', 'Admin', 'Technician'].map(r => (
            <div
              key={r}
              className={`role-tab ${role === r ? 'active' : ''}`}
              onClick={() => setRole(r)}
            >
              {r}
            </div>
          ))}
        </div>

        <button className="btn-primary" type="submit">Sign in</button>
      </form>
    </div>
  );
}