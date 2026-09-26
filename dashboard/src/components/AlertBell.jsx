import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';

function timeAgo(isoTimestamp) {
  const diffMs = Date.now() - new Date(isoTimestamp).getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
}

export default function AlertBell() {
  const [queue, setQueue] = useState([]);
  const [open, setOpen] = useState(false);
  const [readIds, setReadIds] = useState(() => new Set());
  const dropdownRef = useRef(null);

  useEffect(() => {
    const fetchQueue = () => {
      axios.get(`${API}/anomalies/queue`)
        .then(res => setQueue(res.data || []))
        .catch(() => {});
    };
    fetchQueue();
    const interval = setInterval(fetchQueue, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    function handleClickOutside(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const unreadCount = queue.filter(a => !readIds.has(a.id)).length;
  const criticalCount = queue.filter(a => a.severity === 'CRITICAL').length;
  const warningCount = queue.filter(a => a.severity === 'WARNING').length;
  const infoCount = queue.filter(a => a.severity === 'INFO').length;

  function markAllRead() {
    setReadIds(new Set(queue.map(a => a.id)));
  }

  function dismiss(id) {
    setReadIds(prev => new Set(prev).add(id));
  }

  return (
    <div className="alert-bell-wrap" style={{ position: 'relative' }} ref={dropdownRef}>
      <button
        className="alert-bell-btn"
        onClick={() => setOpen(o => !o)}
        style={{
          position: 'relative', background: 'none', border: 'none', cursor: 'pointer',
          fontSize: '1.1rem', padding: '6px'
        }}
        aria-label="System alerts"
      >
        🔔
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute', top: 0, right: 0, background: 'var(--red)', color: '#fff',
            borderRadius: '999px', fontSize: '0.65rem', padding: '1px 5px', fontWeight: 700
          }}>
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: '110%', right: 0, width: 380, maxHeight: 460,
          overflowY: 'auto', background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', boxShadow: 'var(--shadow-hover)', zIndex: 50
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', borderBottom: '1px solid var(--border)'
          }}>
            <strong style={{ color: 'var(--text)' }}>System Alerts</strong>
            <button
              onClick={markAllRead}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: '0.8rem', cursor: 'pointer' }}
            >
              Mark all read
            </button>
          </div>
          <div style={{
            padding: '8px 16px', fontSize: '0.75rem', color: 'var(--text-secondary)',
            borderBottom: '1px solid var(--border)'
          }}>
            {criticalCount} Critical · {warningCount} Warning · {infoCount} Info
          </div>

          {queue.length === 0 ? (
            <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No active alerts.
            </div>
          ) : (
            queue.map(item => {
              const severityColor = item.severity === 'CRITICAL' ? 'var(--red)'
                : item.severity === 'WARNING' ? 'var(--amber)' : 'var(--blue)';
              return (
                <div
                  key={item.id}
                  onClick={() => dismiss(item.id)}
                  style={{
                    padding: '12px 16px', borderLeft: `3px solid ${severityColor}`,
                    borderBottom: '1px solid var(--border)', cursor: 'pointer',
                    opacity: readIds.has(item.id) ? 0.55 : 1,
                    background: 'var(--surface)'
                  }}
                >
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: severityColor, marginBottom: 4 }}>
                    {item.severity} · {item.zone} · {item.facility_type}
                  </div>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 2, color: 'var(--text)' }}>
                    {item.type} — {item.asset}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Voltage {item.voltage} V ({item.deviation_pct}% from nominal) · {item.active_power} kW
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    {timeAgo(item.timestamp)}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}