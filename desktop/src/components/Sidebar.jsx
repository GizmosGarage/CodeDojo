import React from 'react';
import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/dashboard', icon: '\u2302', label: 'Home' },
  { to: '/train', icon: '\u2694', label: 'Train' },
  { to: '/skills', icon: '\u25ce', label: 'Skills' },
];

export default function Sidebar() {
  const handleLeave = () => {
    if (window.electronAPI) {
      window.electronAPI.close();
    }
  };

  return (
    <div className="sidebar">
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            data-tooltip={item.label}
            className={({ isActive }) =>
              `sidebar-nav-item${isActive ? ' active' : ''}`
            }
          >
            <span>{item.icon}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <button
          className="sidebar-leave-btn"
          onClick={handleLeave}
          title="Quit"
        >
          {'\u23FB'}
        </button>
      </div>
    </div>
  );
}
