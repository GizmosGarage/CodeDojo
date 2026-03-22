import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useApi } from '../hooks/useApi';
import { useUser } from '../context/UserContext';
import Quiz from './Quiz';
import Challenge from './Challenge';

export default function BeltExam() {
  const api = useApi();
  const { user, refreshUser } = useUser();
  const navigate = useNavigate();

  const [phase, setPhase] = useState('intro'); // intro, running, complete
  const [examConfig, setExamConfig] = useState(null);
  const [nextBelt, setNextBelt] = useState(null);
  const [beltTarget, setBeltTarget] = useState(null);
  const [loading, setLoading] = useState(true);

  // Exam state
  const [plan, setPlan] = useState([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [roundsPassed, setRoundsPassed] = useState(0);
  const [weakAreas, setWeakAreas] = useState([]);

  // Result
  const [result, setResult] = useState(null);

  useEffect(() => {
    api.get('/belt-exam/readiness').then((data) => {
      if (data.ready) {
        setExamConfig(data.exam_config);
        setNextBelt(data.next_belt);
        setBeltTarget(data.next_rank);
      } else {
        // Not ready — redirect back
        navigate('/dashboard');
      }
    }).catch(() => navigate('/dashboard'))
      .finally(() => setLoading(false));
  }, []);

  const startExam = () => {
    if (!examConfig) return;

    // Build exam plan: quizzes, then challenges, then boss
    const steps = [];
    for (let i = 0; i < examConfig.quizzes; i++) {
      steps.push({ type: 'quiz', index: i + 1, total: examConfig.quizzes, isBoss: false });
    }
    for (let i = 0; i < examConfig.challenges; i++) {
      steps.push({ type: 'challenge', index: i + 1, total: examConfig.challenges, isBoss: false });
    }
    if (examConfig.has_boss) {
      steps.push({ type: 'boss', index: 1, total: 1, isBoss: true });
    }

    setPlan(steps);
    setStepIndex(0);
    setRoundsPassed(0);
    setWeakAreas([]);
    setPhase('running');
  };

  const handleStepComplete = async (stepResult) => {
    const passed = stepResult?.correct || stepResult?.passed || false;
    const currentStep = plan[stepIndex];

    if (passed) {
      setRoundsPassed((prev) => prev + 1);
    } else {
      // Track weak area
      const label = currentStep.isBoss
        ? 'Boss Challenge'
        : currentStep.type === 'quiz'
          ? `Quiz Round ${currentStep.index}`
          : `Challenge ${currentStep.index}`;
      setWeakAreas((prev) => [...prev, label]);
    }

    if (stepIndex + 1 >= plan.length) {
      // Exam complete — submit results
      const totalPassed = passed ? roundsPassed + 1 : roundsPassed;
      const allWeak = passed ? weakAreas : [...weakAreas, 'Final round'];

      try {
        const res = await api.post('/belt-exam/complete', {
          belt_target: beltTarget,
          rounds_passed: totalPassed,
          total_rounds: plan.length,
          weak_areas: allWeak,
        });
        setResult(res);
      } catch {
        setResult({
          passed: false,
          feedback: 'An error occurred evaluating your exam.',
          score: totalPassed,
          total_rounds: plan.length,
        });
      }

      refreshUser();
      setPhase('complete');
    } else {
      setStepIndex((prev) => prev + 1);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ padding: 80 }}>
        <div className="loading-spinner" />
      </div>
    );
  }

  // ── INTRO PHASE ────────────────────────────────────────────────
  if (phase === 'intro' && nextBelt) {
    return (
      <motion.div
        className="text-center"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        style={{ paddingTop: 40 }}
      >
        <div style={{ fontSize: 56, marginBottom: 16 }}>{nextBelt.icon}</div>
        <h1 className="heading-retro" style={{ fontSize: 26, marginBottom: 8 }}>
          {nextBelt.name} Exam
        </h1>
        <p style={{ color: 'var(--text-secondary)', maxWidth: 480, margin: '0 auto 8px' }}>
          {nextBelt.knowledge}
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, maxWidth: 480, margin: '0 auto 32px' }}>
          You must pass <strong>every round</strong> to earn your belt.
          {examConfig && (
            <span>
              {' '}{examConfig.quizzes} quiz round{examConfig.quizzes > 1 ? 's' : ''},
              {' '}{examConfig.challenges} challenge{examConfig.challenges > 1 ? 's' : ''},
              and a final boss challenge.
            </span>
          )}
        </p>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button className="btn btn-primary btn-lg" onClick={startExam}>
            Begin Exam
          </button>
          <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
            Not Yet
          </button>
        </div>
      </motion.div>
    );
  }

  // ── RUNNING PHASE ──────────────────────────────────────────────
  if (phase === 'running' && plan.length > 0) {
    const current = plan[stepIndex];
    const totalSteps = plan.length;
    const progress = (stepIndex / totalSteps) * 100;

    // Determine what type of content to show
    const isBoss = current.isBoss;
    const isQuiz = current.type === 'quiz';

    const roundLabel = isBoss
      ? '\u2694 BOSS CHALLENGE'
      : isQuiz
        ? `Quiz ${current.index}/${current.total}`
        : `Challenge ${current.index}/${current.total}`;

    return (
      <div>
        <div className="flex items-center justify-between mb-md">
          <div>
            <span style={{
              fontSize: 11, fontWeight: 700, color: isBoss ? 'var(--error)' : 'var(--accent)',
              textTransform: 'uppercase', letterSpacing: 1,
            }}>
              {nextBelt?.name} Exam
            </span>
            <h2 className="heading-section" style={{ marginBottom: 0, marginTop: 4 }}>
              {roundLabel}
            </h2>
          </div>
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            Round {stepIndex + 1} of {totalSteps} | {roundsPassed} passed
          </span>
        </div>

        <div className="xp-bar-track mb-md" style={{ height: 4 }}>
          <div className="xp-bar-fill" style={{
            width: `${progress}%`,
            transition: 'width 0.5s',
            background: isBoss ? 'var(--error)' : undefined,
          }} />
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={`exam-${stepIndex}`}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -30 }}
            transition={{ duration: 0.3 }}
          >
            {isQuiz ? (
              <Quiz
                skillId="fundamentals.variables_types"
                difficulty={beltTarget <= 2 ? 'beginner' : beltTarget <= 4 ? 'intermediate' : 'advanced'}
                onComplete={handleStepComplete}
                examMode
              />
            ) : (
              <Challenge
                skillId="fundamentals.variables_types"
                difficulty={beltTarget <= 2 ? 'beginner' : beltTarget <= 4 ? 'intermediate' : 'advanced'}
                onComplete={handleStepComplete}
                examMode
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    );
  }

  // ── COMPLETE PHASE ─────────────────────────────────────────────
  if (phase === 'complete' && result) {
    const passed = result.passed;

    return (
      <motion.div
        className="text-center"
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6 }}
        style={{ paddingTop: 40 }}
      >
        <div style={{ fontSize: 64, marginBottom: 16 }}>
          {passed ? nextBelt?.icon || '\ud83c\udf89' : '\ud83d\udcaa'}
        </div>

        <h1 className="heading-retro" style={{
          fontSize: 24,
          color: passed ? 'var(--accent)' : 'var(--text-primary)',
        }}>
          {passed ? `${nextBelt?.name} Earned!` : 'Not Yet, Student.'}
        </h1>

        <div style={{ maxWidth: 500, margin: '0 auto' }}>
          <div className="card mt-md" style={{ textAlign: 'left' }}>
            <div className="card-title">Score</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: passed ? 'var(--accent)' : 'var(--text-primary)' }}>
              {result.score}/{result.total_rounds} rounds passed
            </div>
          </div>

          {result.feedback && (
            <div className="sensei-message mt-md" style={{ textAlign: 'left' }}>
              <div className="sensei-label">Sensei:</div>
              <div className="sensei-text">{result.feedback}</div>
            </div>
          )}

          {weakAreas.length > 0 && !passed && (
            <div className="card mt-md" style={{ textAlign: 'left' }}>
              <div className="card-title">Areas to Improve</div>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {weakAreas.map((area, i) => (
                  <li key={i} style={{ padding: '4px 0', color: 'var(--text-secondary)', fontSize: 13 }}>
                    {'\u2022'} {area}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="mt-lg flex gap-md justify-center">
          <button className="btn btn-primary btn-lg" onClick={() => navigate('/dashboard')}>
            {passed ? 'Continue' : 'Back to Training'}
          </button>
        </div>
      </motion.div>
    );
  }

  return null;
}
