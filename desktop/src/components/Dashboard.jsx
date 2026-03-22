import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useUser } from '../context/UserContext';
import { useApi } from '../hooks/useApi';

export default function Dashboard() {
  const { user, beltInfo, levelInfo } = useUser();
  const api = useApi();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [examReady, setExamReady] = useState(false);
  const [examDetails, setExamDetails] = useState(null);

  useEffect(() => {
    api.get('/progress').then((data) => {
      setStats(data.stats || null);
      setExamReady(data.belt_exam_ready || false);
      setExamDetails(data.belt_exam_details || null);
    }).catch(() => setStats(null));
  }, []);

  const xp = user?.total_xp || 0;
  const streak = user?.current_streak || 0;
  const level = levelInfo?.level || 1;

  return (
    <div className="page-bg page-bg-home">
      {/* Belt Exam Invitation */}
      {examReady && examDetails?.next_belt && (
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          style={{
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(16, 185, 129, 0.05))',
            border: '1px solid rgba(16, 185, 129, 0.35)',
            borderRadius: 'var(--radius-lg)',
            padding: '20px 24px',
            marginBottom: 24,
            cursor: 'pointer',
            backdropFilter: 'blur(8px)',
          }}
          onClick={() => navigate('/belt-exam')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ fontSize: 32 }}>{examDetails.next_belt.icon}</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--accent)', marginBottom: 2 }}>
                Sensei believes you are ready.
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                Take the {examDetails.next_belt.name} exam to advance your rank.
              </div>
            </div>
            <span style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
              Begin Exam {'\u2192'}
            </span>
          </div>
        </motion.div>
      )}

      {/* Hero Action */}
      <motion.div
        className="action-hero"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="action-hero-title">Ready to train?</div>
        <div className="action-hero-sub">
          Pick up where you left off or start a new session.
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/train')}>
          Start Training
        </button>

        {/* Mini Stats */}
        <div className="mini-stats">
          <div className="mini-stat">
            <span className="mini-stat-value">{xp}</span>
            <span className="mini-stat-label">XP</span>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-value">Lv.{level}</span>
            <span className="mini-stat-label">Level</span>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-value">{beltInfo.current.icon}</span>
            <span className="mini-stat-label">Belt</span>
          </div>
          <div className="mini-stat">
            <span className="mini-stat-value">{streak}</span>
            <span className="mini-stat-label">Streak</span>
          </div>
          {stats && (
            <div className="mini-stat">
              <span className="mini-stat-value">
                {stats.quiz_correct_rate != null ? `${Math.round(stats.quiz_correct_rate * 100)}%` : '--'}
              </span>
              <span className="mini-stat-label">Accuracy</span>
            </div>
          )}
        </div>
      </motion.div>

      {/* Quick Cards at bottom */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.3 }}
      >
        <div className="quick-cards">
          <div className="quick-card" onClick={() => navigate('/train')} style={{ backdropFilter: 'blur(8px)' }}>
            <div className="quick-card-icon">{'\u2694'}</div>
            <div className="quick-card-text">
              <span className="quick-card-label">Quick Session</span>
              <span className="quick-card-desc">5 min focused training</span>
            </div>
          </div>
          <div className="quick-card" onClick={() => navigate('/skills')} style={{ backdropFilter: 'blur(8px)' }}>
            <div className="quick-card-icon">{'\u25ce'}</div>
            <div className="quick-card-text">
              <span className="quick-card-label">Skill Garden</span>
              <span className="quick-card-desc">Browse & pick skills</span>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
