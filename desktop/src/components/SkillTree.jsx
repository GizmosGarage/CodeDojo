import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useApi } from '../hooks/useApi';

function getNodeClass(skill) {
  if (skill.mastered) return 'mastered';
  if (skill.in_progress || skill.progress > 0) return 'in-progress';
  if (skill.locked) return 'locked';
  return 'unlocked';
}

function getNodeIcon(state) {
  switch (state) {
    case 'mastered': return '\ud83c\udf1f';
    case 'in-progress': return '\ud83d\udd36';
    case 'locked': return '\ud83d\udd12';
    default: return '\u25cb';
  }
}

export default function SkillTree() {
  const api = useApi();
  const navigate = useNavigate();
  const [branches, setBranches] = useState([]);
  const [selectedSkill, setSelectedSkill] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get('/skills/tree').then((data) => {
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        const branchArray = Object.entries(data).map(([branchId, branch]) => ({
          id: branchId,
          name: branch.name,
          icon: branch.icon,
          description: branch.description,
          skills: Object.entries(branch.skills || {}).map(([skillId, skill]) => ({
            id: skillId,
            skill_id: skillId,
            ...skill,
            locked: !skill.unlocked,
            mastered: skill.level >= 4,
            in_progress: skill.level >= 1 && skill.level < 4,
            progress: skill.level > 0 ? skill.level / 4 : 0,
            accuracy: skill.correct_rate != null ? skill.correct_rate * 100 : null,
          })),
        }));
        setBranches(branchArray);
      } else {
        setBranches(Array.isArray(data) ? data : []);
      }
    }).catch(() => setBranches([])).finally(() => setLoading(false));
  }, []);

  const handleTrainSkill = (skill) => {
    navigate(`/train?skill=${skill.id}`);
  };

  if (loading) {
    return (
      <div className="page-bg page-bg-garden">
        <h1 className="heading-retro">Skill Garden</h1>
        <div className="flex items-center justify-center" style={{ padding: 60 }}>
          <div className="loading-spinner" />
        </div>
      </div>
    );
  }

  return (
    <div className="page-bg page-bg-garden">
      <h1 className="heading-retro">Skill Garden</h1>

      {branches.length === 0 && (
        <div className="card text-center" style={{ padding: 40 }}>
          <p style={{ color: 'var(--text-muted)' }}>
            No skills data available. Start training to unlock skills!
          </p>
        </div>
      )}

      {branches.map((branch, bi) => (
        <motion.div
          key={branch.id || bi}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: bi * 0.1 }}
          className="mb-lg"
        >
          <div className="flex items-center gap-sm mb-md">
            <span style={{ fontSize: 24 }}>{branch.icon || '\ud83d\udcda'}</span>
            <div>
              <h2 className="heading-section" style={{ marginBottom: 2 }}>
                {branch.name || branch.id}
              </h2>
              {branch.description && (
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>{branch.description}</p>
              )}
            </div>
          </div>

          <div className="skill-tree-grid">
            {(branch.skills || []).map((skill, si) => {
              const state = getNodeClass(skill);
              const isSelected = selectedSkill?.id === skill.id;
              const hasRealProgress = skill.xp > 0 || skill.level > 0;

              return (
                <motion.div
                  key={skill.id || si}
                  className={`skill-node ${state}`}
                  onClick={() => !skill.locked && setSelectedSkill(isSelected ? null : skill)}
                  whileHover={!skill.locked ? { scale: 1.02 } : {}}
                  whileTap={!skill.locked ? { scale: 0.98 } : {}}
                  layout
                >
                  <div className="flex items-center gap-sm mb-sm">
                    <span style={{ fontSize: 20 }}>{getNodeIcon(state)}</span>
                    <span style={{
                      fontWeight: 600,
                      color: state === 'mastered' ? 'var(--accent)' : 'var(--text-primary)',
                    }}>
                      {skill.name || skill.id}
                    </span>
                  </div>

                  {skill.level !== undefined && (
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                      Level {skill.level}
                      {skill.accuracy != null && ` | ${Math.round(skill.accuracy)}% accuracy`}
                    </div>
                  )}

                  {skill.xp !== undefined && (
                    <div style={{ fontSize: 12, color: 'var(--accent-dim)' }}>
                      {skill.xp} XP earned
                    </div>
                  )}

                  {/* Only show progress bar if there's real progress */}
                  {hasRealProgress && !skill.mastered && skill.progress > 0 && (
                    <div className="xp-bar-track mt-sm" style={{ height: 4 }}>
                      <div
                        className="xp-bar-fill"
                        style={{ width: `${Math.min(skill.progress * 100, 100)}%` }}
                      />
                    </div>
                  )}

                  {/* Show empty track for unlocked skills with no progress */}
                  {!hasRealProgress && !skill.locked && (
                    <div className="xp-bar-track mt-sm" style={{ height: 4 }}>
                      <div className="xp-bar-fill" style={{ width: '0%' }} />
                    </div>
                  )}

                  <AnimatePresence>
                    {isSelected && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.06)' }}
                      >
                        {skill.description && (
                          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
                            {skill.description}
                          </p>
                        )}
                        <button
                          className="btn btn-primary btn-sm w-full"
                          onClick={(e) => { e.stopPropagation(); handleTrainSkill(skill); }}
                        >
                          {state === 'mastered' ? 'Practice' : 'Train This Skill'}
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      ))}
    </div>
  );
}
