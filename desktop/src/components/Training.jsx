import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useApi } from '../hooks/useApi';
import { useUser } from '../context/UserContext';
import Quiz from './Quiz';
import Challenge from './Challenge';

const SESSION_TYPES = [
  { id: 'quick', name: 'Quick', desc: '1 quiz + 1 challenge (~5 min)', quizzes: 1, challenges: 1 },
  { id: 'training', name: 'Training', desc: '2 quizzes + 1 challenge (~15 min)', quizzes: 2, challenges: 1 },
  { id: 'deep', name: 'Deep Focus', desc: '3 quizzes + 2 challenges (~30 min)', quizzes: 3, challenges: 2 },
  { id: 'endurance', name: 'Endurance', desc: '5 quizzes + 3 challenges (~45 min)', quizzes: 5, challenges: 3 },
];

export default function Training() {
  const api = useApi();
  const { user, refreshUser } = useUser();
  const [phase, setPhase] = useState('select');
  const [selectedOption, setSelectedOption] = useState(null);
  const [recommendedSkill, setRecommendedSkill] = useState(null);
  const [trainingPlan, setTrainingPlan] = useState([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [sessionXp, setSessionXp] = useState(0);
  const [sessionResults, setSessionResults] = useState([]);
  const [currentSkill, setCurrentSkill] = useState(null);

  useEffect(() => {
    api.get('/skills/recommended').then((data) => {
      if (Array.isArray(data) && data.length > 0) {
        setRecommendedSkill(data[0]);
      }
    }).catch(() => setRecommendedSkill(null));
  }, []);

  const startTraining = () => {
    if (!selectedOption) return;

    if (selectedOption.type === 'recommended') {
      setCurrentSkill(recommendedSkill);
      const plan = [
        { type: 'quiz', index: 1, total: 1 },
        { type: 'challenge', index: 1, total: 1 },
      ];
      setTrainingPlan(plan);
    } else {
      const sessionType = selectedOption.session;
      const plan = [];
      let qi = 0;
      let ci = 0;

      while (qi < sessionType.quizzes || ci < sessionType.challenges) {
        if (qi < sessionType.quizzes) {
          plan.push({ type: 'quiz', index: qi + 1, total: sessionType.quizzes });
          qi++;
        }
        if (ci < sessionType.challenges) {
          plan.push({ type: 'challenge', index: ci + 1, total: sessionType.challenges });
          ci++;
        }
      }
      setTrainingPlan(plan);
    }

    setStepIndex(0);
    setSessionXp(0);
    setSessionResults([]);
    setPhase('training');
  };

  const handleStepComplete = (result) => {
    const earned = result?.xp_earned || 0;
    setSessionXp((prev) => prev + earned);
    setSessionResults((prev) => [...prev, { ...result, step: trainingPlan[stepIndex] }]);

    if (stepIndex + 1 >= trainingPlan.length) {
      setPhase('complete');
      refreshUser();
    } else {
      setStepIndex((prev) => prev + 1);
    }
  };

  const handleRestart = () => {
    setPhase('select');
    setSelectedOption(null);
    setTrainingPlan([]);
    setStepIndex(0);
    setCurrentSkill(null);
  };

  if (phase === 'select') {
    return (
      <div className="page-bg page-bg-train">
        <h1 className="heading-retro">Training Dojo</h1>

        <div className="heading-section mt-lg">Choose Your Session</div>

        {/* Recommended skill — big red standout */}
        {recommendedSkill && (
          <motion.div
            className={`session-option recommended${selectedOption?.id === 'recommended' ? ' selected' : ''}`}
            onClick={() => setSelectedOption({
              id: 'recommended', type: 'recommended',
              name: recommendedSkill.name || recommendedSkill.skill_id,
              desc: 'Your weakest skill — focused practice',
            })}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ marginBottom: 12, backdropFilter: 'blur(8px)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 24 }}>{'\u26a0'}</span>
              <div>
                <div className="session-name">
                  Recommended: {recommendedSkill.name || recommendedSkill.skill_id}
                </div>
                <div className="session-desc">
                  Your weakest skill — focused practice to strengthen your foundation
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Session type options */}
        <div className="session-options">
          {SESSION_TYPES.map((st) => (
            <motion.div
              key={st.id}
              className={`session-option${selectedOption?.id === st.id ? ' selected' : ''}`}
              onClick={() => setSelectedOption({
                id: st.id, type: 'session', session: st, name: st.name, desc: st.desc,
              })}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              style={{ backdropFilter: 'blur(8px)' }}
            >
              <div className="session-name">{st.name}</div>
              <div className="session-desc">{st.desc}</div>
            </motion.div>
          ))}
        </div>

        <div className="mt-lg">
          <button
            className="btn btn-primary btn-lg"
            disabled={!selectedOption}
            onClick={startTraining}
          >
            Begin Training
          </button>
        </div>
      </div>
    );
  }

  if (phase === 'training') {
    const current = trainingPlan[stepIndex];
    const totalSteps = trainingPlan.length;
    const progress = ((stepIndex) / totalSteps) * 100;
    const skillId = currentSkill?.skill_id || 'python_basics';

    return (
      <div className="page-bg page-bg-train">
        <div className="flex items-center justify-between mb-md">
          <h2 className="heading-section" style={{ marginBottom: 0 }}>
            {current.type === 'quiz' ? 'Quiz' : 'Challenge'} {current.index}/{current.total}
          </h2>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Step {stepIndex + 1} of {totalSteps} | +{sessionXp} XP
          </span>
        </div>

        <div className="xp-bar-track mb-md" style={{ height: 4 }}>
          <div className="xp-bar-fill" style={{ width: `${progress}%`, transition: 'width 0.5s' }} />
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={`${current.type}-${stepIndex}`}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.3 }}
          >
            {current.type === 'quiz' ? (
              <Quiz
                skillId={skillId}
                difficulty={user?.current_difficulty || 'beginner'}
                onComplete={handleStepComplete}
              />
            ) : (
              <Challenge
                skillId={skillId}
                difficulty={user?.current_difficulty || 'beginner'}
                onComplete={handleStepComplete}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    );
  }

  if (phase === 'complete') {
    const correct = sessionResults.filter((r) => r.correct || r.passed).length;
    return (
      <motion.div
        className="page-bg page-bg-train text-center"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        style={{ paddingTop: 60 }}
      >
        <div style={{ fontSize: 64, marginBottom: 16 }}>{'\ud83c\udf89'}</div>
        <h1 className="heading-retro">Training Complete!</h1>

        <div className="stats-grid mt-lg" style={{ maxWidth: 500, margin: '24px auto' }}>
          <div className="card stat-card" style={{ backdropFilter: 'blur(8px)' }}>
            <span className="stat-value" style={{ color: 'var(--accent)' }}>+{sessionXp}</span>
            <span className="stat-label">XP Earned</span>
          </div>
          <div className="card stat-card" style={{ backdropFilter: 'blur(8px)' }}>
            <span className="stat-value">{correct}/{sessionResults.length}</span>
            <span className="stat-label">Passed</span>
          </div>
        </div>

        <div className="mt-lg flex gap-md justify-center">
          <button className="btn btn-primary btn-lg" onClick={handleRestart}>
            Train Again
          </button>
        </div>
      </motion.div>
    );
  }

  return null;
}
