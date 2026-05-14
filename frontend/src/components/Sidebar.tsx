import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';

const links = [
  { to: '/', label: 'Big 5', icon: '📊', exact: true },
  { to: '/screener', label: 'Screener', icon: '🔍', exact: false },
  { to: '/forward', label: 'Forward Testing', icon: '🧪', exact: false },
  { to: '/journal', label: 'Journal', icon: '📓', exact: false },
  { to: '/ep', label: 'EP Scanner', icon: '⚡', exact: false },
];

export function Sidebar() {
  const [light, setLight] = useState(() => localStorage.getItem('theme') === 'light');

  useEffect(() => {
    document.body.classList.toggle('light-mode', light);
    localStorage.setItem('theme', light ? 'light' : 'dark');
  }, [light]);

  return (
    <div
      style={{
        position: 'fixed', top: 0, left: 0, height: '100vh', width: 200,
        background: '#13151F', borderRight: '1px solid #2A2D3E',
        display: 'flex', flexDirection: 'column', zIndex: 100,
      }}
    >
      <div style={{ padding: '20px 16px 24px', borderBottom: '1px solid #2A2D3E' }}>
        <p style={{ color: '#00C48C', fontWeight: 700, fontSize: 14, letterSpacing: '0.05em' }}>
          BACKTEST
        </p>
        <p style={{ color: '#8B8FA8', fontSize: 11, marginTop: 2 }}>EMA200 Platform</p>
      </div>
      <nav style={{ flex: 1, padding: '12px 0' }}>
        {links.map(link => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.exact}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 16px',
              borderLeft: isActive ? '3px solid #00C48C' : '3px solid transparent',
              background: isActive ? 'rgba(0,196,140,0.06)' : 'transparent',
              color: isActive ? '#E8EAED' : '#8B8FA8',
              fontSize: 13, fontWeight: isActive ? 600 : 400,
              textDecoration: 'none', transition: 'all 0.15s',
            })}
          >
            <span style={{ fontSize: 15 }}>{link.icon}</span>
            {link.label}
          </NavLink>
        ))}
      </nav>
      <div style={{ padding: '12px 16px', borderTop: '1px solid #2A2D3E' }}>
        <button
          onClick={() => setLight(v => !v)}
          style={{
            width: '100%', padding: '8px 0', borderRadius: 6, border: '1px solid #2A2D3E',
            background: 'transparent', color: '#8B8FA8', fontSize: 12, cursor: 'pointer',
          }}
        >
          {light ? '🌙 Dark' : '☀️ Light'}
        </button>
      </div>
    </div>
  );
}
