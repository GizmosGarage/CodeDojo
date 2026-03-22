import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../context/UserContext';

export default function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false);
  const { user, beltInfo, levelInfo } = useUser();
  const navigate = useNavigate();

  useEffect(() => {
    if (window.electronAPI) {
      window.electronAPI.isMaximized().then(setIsMaximized);
      const cleanup = window.electronAPI.onMaximizeChange(setIsMaximized);
      return cleanup;
    }
  }, []);

  const handleMinimize = () => {
    if (window.electronAPI) window.electronAPI.minimize();
  };

  const handleMaximize = () => {
    if (window.electronAPI) window.electronAPI.maximize();
  };

  const handleClose = () => {
    if (window.electronAPI) window.electronAPI.close();
  };

  return (
    <div className="titlebar">
      <div className="titlebar-title">
        <span style={{ fontSize: 16 }}>{'\u2666'}</span>
        <span>CODEDOJO</span>
      </div>

      <div className="titlebar-right">
        {user && (
          <button
            className="profile-avatar-btn"
            onClick={() => navigate('/profile')}
            title={`${user.name} — ${beltInfo?.current?.name || 'White Belt'} — Lv.${levelInfo?.level || 1}`}
          >
            <span>{beltInfo?.current?.icon || '\u2b1c'}</span>
            <span className="avatar-level">{levelInfo?.level || 1}</span>
          </button>
        )}

        <div className="titlebar-controls">
          <button className="titlebar-btn" onClick={handleMinimize} aria-label="Minimize">
            <svg width="10" height="1" viewBox="0 0 10 1">
              <line x1="0" y1="0.5" x2="10" y2="0.5" stroke="currentColor" strokeWidth="1" />
            </svg>
          </button>
          <button className="titlebar-btn" onClick={handleMaximize} aria-label="Maximize">
            {isMaximized ? (
              <svg width="10" height="10" viewBox="0 0 10 10">
                <rect x="2" y="0" width="8" height="8" fill="none" stroke="currentColor" strokeWidth="1" />
                <rect x="0" y="2" width="8" height="8" fill="var(--bg-deep)" stroke="currentColor" strokeWidth="1" />
              </svg>
            ) : (
              <svg width="10" height="10" viewBox="0 0 10 10">
                <rect x="0" y="0" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1" />
              </svg>
            )}
          </button>
          <button className="titlebar-btn close" onClick={handleClose} aria-label="Close">
            <svg width="10" height="10" viewBox="0 0 10 10">
              <line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" strokeWidth="1.2" />
              <line x1="10" y1="0" x2="0" y2="10" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
