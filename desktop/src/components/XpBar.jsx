import React from 'react';
import { motion } from 'framer-motion';
import { useUser } from '../context/UserContext';

export default function XpBar({ currentXp, compact = false }) {
  const { levelInfo } = useUser();
  const percentage = Math.min(levelInfo.progress * 100, 100);

  const label = `${levelInfo.xpInLevel}/${levelInfo.xpNeeded} XP to Level ${levelInfo.level + 1}`;

  return (
    <div className={`xp-bar-container${compact ? ' xp-bar-compact' : ''}`}>
      {!compact && (
        <div className="flex items-center justify-between mb-sm">
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)' }}>
            Lv. {levelInfo.level}
          </span>
          <span style={{ fontSize: 14, opacity: 0.4 }}>
            Lv. {levelInfo.level + 1}
          </span>
        </div>
      )}
      <div className="xp-bar-track">
        <motion.div
          className="xp-bar-fill"
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 1, ease: 'easeOut' }}
        />
      </div>
      <div className="xp-bar-label">
        <span>{label}</span>
        {!compact && <span style={{ color: 'var(--accent)' }}>{currentXp} XP total</span>}
      </div>
    </div>
  );
}
