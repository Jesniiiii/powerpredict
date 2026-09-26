import { useState } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [keepSignedIn, setKeepSignedIn] = useState(true);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const form = new URLSearchParams();
      form.append('username', username);
      form.append('password', password);

      const loginRes = await axios.post(`${API}/auth/login`, form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      const token = loginRes.data.access_token;

      const meRes = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      onLogin(token, meRes.data.role, meRes.data.full_name, keepSignedIn);
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Incorrect email or password.');
      } else {
        setError('Could not reach the API. Is the FastAPI server running?');
      }
    }
    setSubmitting(false);
  }

  const features = [
    {
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
          <polyline points="17 6 23 6 23 12" />
        </svg>
      ),
      title: 'Zero-shot load forecasting',
      sub: 'Chronos-Bolt · MAPE 15.93% · R² 0.9469'
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      ),
      title: 'Real-time anomaly detection',
      sub: 'Autoencoder reconstruction · 1s telemetry cadence'
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      ),
      title: 'Predictive maintenance diagnosis',
      sub: '4 fault categories · repair urgency by zone tier'
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
      ),
      title: 'Zone criticality tiering',
      sub: 'Critical → Low · geo-linked to transformers'
    }
  ];

  return (
    <div className="login-split">
      <style>{`
        .login-split { display: flex; min-height: 100vh; font-family: inherit; }
        .login-left {
          flex: 1; background: #0a1424; color: #fff; padding: 56px;
          display: flex; flex-direction: column; justify-content: space-between;
          background-image:
            radial-gradient(circle at 15% 15%, rgba(30,60,110,0.5) 0%, transparent 55%),
            linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
          background-size: 100% 100%, 28px 28px, 28px 28px;
        }
        .login-right {
          flex: 1; background: #eef1f6; display: flex; align-items: center;
          justify-content: center; padding: 48px;
        }
        .login-brand-row { display: flex; align-items: center; gap: 12px; margin-bottom: 56px; }
        .login-seal-lg {
          width: 40px; height: 40px; border-radius: 10px;
          background: linear-gradient(135deg, #2dd4bf, #0e7c7b);
          display: flex; align-items: center; justify-content: center;
        }
        .login-brand-text { line-height: 1.2; }
        .login-brand-title { font-weight: 700; font-size: 18px; }
        .login-brand-sub { font-size: 11px; letter-spacing: 0.05em; color: #7a90b8; }
        .login-headline { font-size: 38px; font-weight: 800; line-height: 1.15; max-width: 480px; }
        .login-headline .accent { color: #2dd4bf; }
        .login-blurb { color: #a9b8cc; max-width: 460px; margin-top: 18px; line-height: 1.55; font-size: 14.5px; }
        .login-features { margin-top: 36px; display: flex; flex-direction: column; gap: 20px; max-width: 460px; }
        .login-feature { display: flex; gap: 14px; align-items: flex-start; }
        .login-feature-icon {
          width: 36px; height: 36px; border-radius: 9px; flex-shrink: 0;
          background: rgba(45,212,191,0.12); color: #2dd4bf;
          display: flex; align-items: center; justify-content: center;
        }
        .login-feature-title { font-size: 14.5px; font-weight: 600; color: #fff; }
        .login-feature-sub { font-size: 12px; color: #7a90b8; margin-top: 2px; }
        .login-footer { font-size: 12px; color: #7a90b8; display: flex; align-items: center; gap: 8px; }
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
        .login-row-between { display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 20px; }
        .login-check { display: flex; align-items: center; gap: 6px; color: #4b5563; }
        .forgot-link { color: #3a5aa8; cursor: pointer; }
        .btn-primary {
          width: 100%; background: #0b1a3a; color: #fff; border: none; border-radius: 8px;
          padding: 12px; font-weight: 600; font-size: 14px; cursor: pointer;
        }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
        .login-error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; border-radius: 8px; padding: 10px 12px; font-size: 13px; margin-bottom: 16px; }
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
              <div className="login-brand-sub">GRID OPS CONSOLE</div>
            </div>
          </div>

          <div className="login-headline">
            Forecast the load.<br />
            Catch the fault <span className="accent">before it happens.</span>
          </div>

          <div className="login-blurb">
            AI-driven grid operations — live demand forecasting, automated fault
            diagnosis, and zone-aware anomaly detection for distribution networks.
          </div>

          <div className="login-features">
            {features.map((f, i) => (
              <div className="login-feature" key={i}>
                <div className="login-feature-icon">{f.icon}</div>
                <div>
                  <div className="login-feature-title">{f.title}</div>
                  <div className="login-feature-sub">{f.sub}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="login-footer">
          <span className="login-footer-dot"></span>
          Live feed connected
        </div>
      </div>

      <div className="login-right">
        <form className="login-form-card" onSubmit={handleSubmit}>
          <div className="login-form-title">Sign in to the console</div>
          <div className="login-form-sub">Enter your grid operations credentials.</div>

          {error && <div className="login-error">{error}</div>}

          <div className="field-group">
            <label className="field-label">Email</label>
            <div className="field-input-wrap">
              <input
                type="email"
                placeholder="you@powerpredict.io"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
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
                autoComplete="current-password"
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
          </div>

          <button className="btn-primary" type="submit" disabled={submitting}>
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}