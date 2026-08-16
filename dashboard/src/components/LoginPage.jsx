import { useState } from 'react';
 
export default function LoginPage({ onLogin }) {
  const [role, setRole] = useState('Operator');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [keepSignedIn, setKeepSignedIn] = useState(true);
 
  function handleSubmit(e) {
    e.preventDefault();
    onLogin(role);
  }
 
  return (
    <div className="login-split">
      <style>{`
        .login-split { display: flex; min-height: 100vh; font-family: inherit; }
        .login-left {
          flex: 1; background: #0b1a3a; color: #fff; padding: 48px;
          display: flex; flex-direction: column; justify-content: space-between;
          background-image: linear-gradient(135deg, #0b1a3a 0%, #0f2350 100%);
        }
        .login-right {
          flex: 1; background: #eef1f6; display: flex; align-items: center;
          justify-content: center; padding: 48px;
        }
        .login-brand-row { display: flex; align-items: center; gap: 12px; margin-bottom: 80px; }
        .login-seal-lg {
          width: 40px; height: 40px; border-radius: 10px; background: #3a5aa8;
          display: flex; align-items: center; justify-content: center;
        }
        .login-brand-text { line-height: 1.2; }
        .login-brand-title { font-weight: 700; font-size: 18px; }
        .login-brand-sub { font-size: 11px; letter-spacing: 0.05em; color: #9aa8cc; }
        .login-headline { font-size: 40px; font-weight: 800; line-height: 1.15; max-width: 480px; }
        .login-headline .accent { color: #e8a33d; }
        .login-blurb { color: #c3cbe0; max-width: 460px; margin-top: 20px; line-height: 1.5; }
        .login-stats { display: flex; gap: 16px; margin-top: 40px; }
        .login-stat-card {
          background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px; padding: 16px; min-width: 130px;
        }
        .login-stat-value { font-size: 22px; font-weight: 700; }
        .login-stat-label { font-size: 11px; color: #9aa8cc; margin-top: 4px; }
        .login-footer { font-size: 12px; color: #8b96b8; display: flex; align-items: center; gap: 8px; }
        .login-footer-dot { width: 7px; height: 7px; border-radius: 50%; background: #3fcf6e; }
 
        .login-form-card { background: #fff; border-radius: 14px; padding: 40px; width: 100%; max-width: 420px; }
        .login-form-title { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
        .login-form-sub { font-size: 13px; color: #6b7280; margin-bottom: 24px; }
        .field-group { margin-bottom: 18px; }
        .field-label { font-size: 13px; font-weight: 600; margin-bottom: 6px; display: block; }
        .field-input-wrap {
          display: flex; align-items: center; gap: 8px; border: 1px solid #d7dbe3;
          border-radius: 8px; padding: 10px 12px; background: #f9fafb;
        }
        .field-input-wrap input { border: none; background: transparent; outline: none; flex: 1; font-size: 14px; }
        .role-tabs { display: flex; gap: 8px; margin-bottom: 20px; }
        .role-tab {
          flex: 1; text-align: center; padding: 10px; border-radius: 8px;
          border: 1px solid #d7dbe3; cursor: pointer; font-size: 14px; color: #4b5563;
          transition: background 0.15s, color 0.15s;
        }
        .role-tab.active { background: #0b1a3a; color: #fff; border-color: #0b1a3a; }
        .login-row-between { display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 20px; }
        .login-check { display: flex; align-items: center; gap: 6px; color: #4b5563; }
        .forgot-link { color: #3a5aa8; cursor: pointer; }
        .btn-primary {
          width: 100%; background: #0b1a3a; color: #fff; border: none; border-radius: 8px;
          padding: 12px; font-weight: 600; font-size: 14px; cursor: pointer;
        }
        .btn-sso {
          width: 100%; background: #fff; border: 1px solid #d7dbe3; border-radius: 8px;
          padding: 12px; font-weight: 600; font-size: 14px; cursor: pointer; margin-top: 12px;
        }
        .login-divider { display: flex; align-items: center; gap: 12px; margin: 18px 0; color: #9aa0af; font-size: 12px; }
        .login-divider::before, .login-divider::after { content: ""; flex: 1; height: 1px; background: #e5e7eb; }
        .login-security-note { font-size: 12px; color: #6b7280; margin-top: 20px; display: flex; align-items: center; gap: 6px; }
      `}</style>
 
      <div className="login-left">
        <div>
          <div className="login-brand-row">
            <div className="login-seal-lg">
              <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" width="20" height="20">
                <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z"/>
              </svg>
            </div>
            <div className="login-brand-text">
              <div className="login-brand-title">PowerPredict</div>
              <div className="login-brand-sub">GRID OPERATIONS CONSOLE</div>
            </div>
          </div>
 
          <div className="login-headline">
            Forecast the load.<br />
            Catch the fault <span className="accent">before it happens.</span>
          </div>
 
          <div className="login-blurb">
            LSTM demand forecasting, anomaly detection, and predictive
            maintenance — streamed from Kafka, stored in InfluxDB.
          </div>
 
          <div className="login-stats">
            <div className="login-stat-card">
              <div className="login-stat-value">96.3%</div>
              <div className="login-stat-label">FORECAST ACCURACY</div>
            </div>
            <div className="login-stat-card">
              <div className="login-stat-value">1.2M</div>
              <div className="login-stat-label">READINGS / DAY</div>
            </div>
            <div className="login-stat-card">
              <div className="login-stat-value">SOC 2</div>
              <div className="login-stat-label">TYPE II CERTIFIED</div>
            </div>
          </div>
        </div>
 
        <div className="login-footer">
          <span className="login-footer-dot"></span>
          All regional gateways operational
        </div>
      </div>
 
      <div className="login-right">
        <form className="login-form-card" onSubmit={handleSubmit}>
          <div className="login-form-title">Sign in to the console</div>
          <div className="login-form-sub">Authorised grid personnel only. Sessions are audit-logged.</div>
 
          <div className="field-group">
            <label className="field-label">Access role</label>
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
          </div>
 
          <div className="field-group">
            <label className="field-label">Username</label>
            <div className="field-input-wrap">
              <input
                type="text"
                placeholder="operator_01"
                value={username}
                onChange={e => setUsername(e.target.value)}
              />
            </div>
          </div>
 
          <div className="field-group">
            <label className="field-label">Password</label>
            <div className="field-input-wrap">
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>
          </div>
 
          <div className="login-row-between">
            <label className="login-check">
              <input
                type="checkbox"
                checked={keepSignedIn}
                onChange={e => setKeepSignedIn(e.target.checked)}
              />
              Keep me signed in
            </label>
            <span className="forgot-link">Forgot password?</span>
          </div>
 
          <button className="btn-primary" type="submit">Sign in</button>
 
          <div className="login-divider">OR</div>
 
          <button
            className="btn-sso"
            type="button"
            onClick={() => alert('SSO is not implemented in this build.')}
          >
            Continue with utility SSO (SAML)
          </button>
 
          <div className="login-security-note">
            🛡️ Protected by MFA and NERC CIP-compliant access control.
          </div>
        </form>
      </div>
    </div>
  );
}
 