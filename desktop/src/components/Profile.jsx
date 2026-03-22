import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useUser, BELT_CONFIG } from '../context/UserContext';
import { useApi } from '../hooks/useApi';
import XpBar from './XpBar';

export default function Profile() {
  const { user, beltInfo, levelInfo } = useUser();
  const api = useApi();
  const [stats, setStats] = useState(null);
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    api.get('/progress').then((data) => {
      setStats(data.stats || null);
    }).catch(() => setStats(null));

    api.get('/sessions?limit=10').then((data) => {
      setSessions(Array.isArray(data) ? data : []);
    }).catch(() => setSessions([]));
  }, []);

  const xp = user?.total_xp || 0;
  const streak = user?.current_streak || 0;
  const beltRank = user?.belt_rank || 0;
  const level = levelInfo?.level || 1;

  return (
    <div className="profile-page page-bg page-bg-bedroom">
      {/* Header */}
      <motion.div
        className="profile-header"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="profile-avatar-large">
          <span>{beltInfo.current.icon}</span>
          <span className="avatar-level-lg">{level}</span>
        </div>
        <div className="profile-info">
          <h2>{user?.name || 'Student'}</h2>
          <p>
            {beltInfo.current.name} — Level {level} — {xp} XP
          </p>
        </div>
      </motion.div>

      {/* Level Progress */}
      <motion.div
        className="card mb-lg"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <div className="card-title">Level Progress</div>
        <XpBar currentXp={xp} />
      </motion.div>

      {/* Stats Grid */}
      <motion.div
        className="profile-stats-grid"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15 }}
      >
        <div className="profile-stat-card">
          <span className="stat-value" style={{ color: 'var(--accent)' }}>Lv.{level}</span>
          <span className="stat-label">Level</span>
        </div>
        <div className="profile-stat-card">
          <span className="stat-value">{streak}</span>
          <span className="stat-label">Day Streak</span>
        </div>
        <div className="profile-stat-card">
          <span className="stat-value">{stats?.challenges_passed || 0}</span>
          <span className="stat-label">Challenges</span>
        </div>
        <div className="profile-stat-card">
          <span className="stat-value">
            {stats?.quiz_correct_rate != null ? `${Math.round(stats.quiz_correct_rate * 100)}%` : '--'}
          </span>
          <span className="stat-label">Accuracy</span>
        </div>
        <div className="profile-stat-card">
          <span className="stat-value">{stats?.sessions_completed || user?.sessions_completed || 0}</span>
          <span className="stat-label">Sessions</span>
        </div>
        <div className="profile-stat-card">
          <span className="stat-value">{stats?.skills_unlocked || 0}</span>
          <span className="stat-label">Skills</span>
        </div>
      </motion.div>

      {/* Belt Roadmap */}
      <motion.div
        className="card mb-lg"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        <div className="card-title">Belt Roadmap</div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
          Belts are earned by passing exams — not by XP alone.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {BELT_CONFIG.map((belt, i) => {
            const earned = beltRank >= belt.rank;
            const isCurrent = beltRank === belt.rank;
            return (
              <div
                key={belt.name}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 4,
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  background: earned ? 'var(--accent-subtle)' : 'var(--bg-panel)',
                  border: isCurrent ? '1px solid var(--accent)' : 'var(--border-subtle)',
                  opacity: earned ? 1 : 0.4,
                  minWidth: 64,
                }}
              >
                <span style={{ fontSize: 20 }}>{belt.icon}</span>
                <span style={{ fontSize: 9, color: 'var(--text-muted)', textAlign: 'center' }}>
                  {earned ? '\u2713' : 'Exam'}
                </span>
              </div>
            );
          })}
        </div>
      </motion.div>

      {/* Recent Sessions */}
      {sessions.length > 0 && (
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <div className="card-title">Recent Sessions</div>
          <ul className="session-list">
            {sessions.map((session, i) => (
              <li key={session.id || i} className="session-item">
                <div className="session-item-left">
                  <span>{session.type === 'quiz' ? '\u270D' : '\u2328'}</span>
                  <span>{session.skill || session.type || 'Training'}</span>
                </div>
                <div className="flex items-center gap-md">
                  <span className="session-item-xp">+{session.xp_earned || 0} XP</span>
                  <span className="session-item-date">
                    {session.date ? new Date(session.date).toLocaleDateString() : ''}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  );
}
