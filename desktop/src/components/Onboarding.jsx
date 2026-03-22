import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useApi } from '../hooks/useApi';
import { useUser, getBeltInfo } from '../context/UserContext';

const ASSESSMENT_QUESTIONS = [
  {
    question: 'What does `print("Hello")` do in Python?',
    options: [
      'Displays "Hello" on the screen',
      'Creates a variable named Hello',
      'Defines a function called Hello',
      'Nothing, it causes an error',
    ],
    correct: 0,
  },
  {
    question: 'Which of these is a valid Python list?',
    options: [
      '{1, 2, 3}',
      '[1, 2, 3]',
      '(1, 2, 3)',
      '<1, 2, 3>',
    ],
    correct: 1,
  },
  {
    question: 'What does `len([1, 2, 3])` return?',
    options: ['1', '2', '3', '4'],
    correct: 2,
  },
  {
    question: 'How do you define a function in Python?',
    options: [
      'function myFunc():',
      'def myFunc():',
      'fn myFunc():',
      'func myFunc():',
    ],
    correct: 1,
  },
  {
    question: 'What is the output of `2 ** 3`?',
    options: ['5', '6', '8', '9'],
    correct: 2,
  },
];

const pageVariants = {
  enter: { opacity: 0, x: 50 },
  center: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -50 },
};

export default function Onboarding() {
  const navigate = useNavigate();
  const api = useApi();
  const { refreshUser } = useUser();
  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [assessmentIndex, setAssessmentIndex] = useState(0);
  const [assessmentAnswers, setAssessmentAnswers] = useState([]);
  const [selectedOption, setSelectedOption] = useState(null);
  const [assessmentScore, setAssessmentScore] = useState(0);
  const [placedBelt, setPlacedBelt] = useState(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  const handleEnterDojo = () => setStep(1);

  const handleNameSubmit = () => {
    if (name.trim()) setStep(2);
  };

  const handleStartAssessment = () => {
    setStep(3);
    setAssessmentIndex(0);
    setAssessmentAnswers([]);
    setSelectedOption(null);
  };

  const handleSkipAssessment = () => {
    finishOnboarding(0);
  };

  const handleAnswerSelect = (idx) => {
    setSelectedOption(idx);
  };

  const handleAnswerSubmit = () => {
    if (selectedOption === null) return;
    const q = ASSESSMENT_QUESTIONS[assessmentIndex];
    const isCorrect = selectedOption === q.correct;
    const newAnswers = [...assessmentAnswers, { selected: selectedOption, correct: isCorrect }];
    setAssessmentAnswers(newAnswers);

    if (assessmentIndex + 1 < ASSESSMENT_QUESTIONS.length) {
      setAssessmentIndex(assessmentIndex + 1);
      setSelectedOption(null);
    } else {
      const score = newAnswers.filter((a) => a.correct).length;
      setAssessmentScore(score);
      finishOnboarding(score);
    }
  };

  const finishOnboarding = async (score) => {
    setCreating(true);
    setError(null);

    let startingXp = 0;
    if (score >= 5) startingXp = 100;
    else if (score >= 3) startingXp = 50;

    const belt = getBeltInfo(startingXp);
    setPlacedBelt(belt);
    setStep(4);

    try {
      await api.post('/user', {
        name: name.trim(),
      });
      await refreshUser();
    } catch {
      setError('Failed to create profile. You can try again from the dashboard.');
    } finally {
      setCreating(false);
    }
  };

  const handleFinish = () => {
    navigate('/dashboard');
  };

  return (
    <div className="onboarding-screen">
      <AnimatePresence mode="wait">
        {/* Step 0: Welcome */}
        {step === 0 && (
          <motion.div
            key="welcome"
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.4 }}
            className="text-center"
          >
            <motion.div
              style={{ fontSize: 80, marginBottom: 16 }}
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              {'\ud83e\udd4b'}
            </motion.div>
            <h1 className="onboarding-title">CodeDojo</h1>
            <p className="onboarding-subtitle">
              Master Python through the way of the code warrior
            </p>
            <motion.button
              className="btn btn-primary btn-lg"
              onClick={handleEnterDojo}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              style={{
                fontSize: 18,
                letterSpacing: 2,
                textTransform: 'uppercase',
                padding: '16px 40px',
              }}
            >
              Enter the Dojo
            </motion.button>
          </motion.div>
        )}

        {/* Step 1: Name Input */}
        {step === 1 && (
          <motion.div
            key="name"
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.4 }}
            className="text-center"
            style={{ maxWidth: 400, width: '100%' }}
          >
            <div style={{ fontSize: 48, marginBottom: 16 }}>{'\ud83e\uddd1\u200d\ud83c\udfeb'}</div>
            <h2 className="heading-retro" style={{ fontSize: 20 }}>
              What is your name, student?
            </h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>
              Every warrior needs a name.
            </p>
            <input
              className="input"
              style={{ textAlign: 'center', fontSize: 18, marginBottom: 20 }}
              placeholder="Enter your name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleNameSubmit()}
              autoFocus
            />
            <button
              className="btn btn-primary btn-lg w-full"
              onClick={handleNameSubmit}
              disabled={!name.trim()}
            >
              Continue
            </button>
          </motion.div>
        )}

        {/* Step 2: Assessment Offer */}
        {step === 2 && (
          <motion.div
            key="assessment-offer"
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.4 }}
            className="text-center"
            style={{ maxWidth: 440, width: '100%' }}
          >
            <div style={{ fontSize: 48, marginBottom: 16 }}>{'\u2694\ufe0f'}</div>
            <h2 className="heading-retro" style={{ fontSize: 20 }}>
              Ready for the Assessment?
            </h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>
              Welcome, <span style={{ color: 'var(--gold)' }}>{name}</span>.
            </p>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 32 }}>
              Take a short assessment to determine your starting belt, or begin as a White Belt.
            </p>
            <div className="flex flex-col gap-md">
              <button className="btn btn-primary btn-lg w-full" onClick={handleStartAssessment}>
                Take Assessment
              </button>
              <button className="btn btn-secondary w-full" onClick={handleSkipAssessment}>
                Skip (Start as White Belt)
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 3: Assessment Questions */}
        {step === 3 && (
          <motion.div
            key={`q-${assessmentIndex}`}
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.3 }}
            style={{ maxWidth: 520, width: '100%' }}
          >
            <div className="flex items-center justify-between mb-md">
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                Question {assessmentIndex + 1} of {ASSESSMENT_QUESTIONS.length}
              </span>
              <div className="xp-bar-track" style={{ height: 4, width: 120 }}>
                <div
                  className="xp-bar-fill"
                  style={{ width: `${((assessmentIndex) / ASSESSMENT_QUESTIONS.length) * 100}%` }}
                />
              </div>
            </div>

            <div className="card">
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, lineHeight: 1.5 }}>
                {ASSESSMENT_QUESTIONS[assessmentIndex].question}
              </h3>

              <div className="quiz-options">
                {ASSESSMENT_QUESTIONS[assessmentIndex].options.map((opt, idx) => (
                  <button
                    key={idx}
                    className={`quiz-option${selectedOption === idx ? ' selected' : ''}`}
                    onClick={() => handleAnswerSelect(idx)}
                  >
                    <span style={{
                      display: 'inline-block',
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      border: '2px solid currentColor',
                      textAlign: 'center',
                      lineHeight: '18px',
                      fontSize: 11,
                      marginRight: 8,
                      opacity: 0.6,
                    }}>
                      {String.fromCharCode(65 + idx)}
                    </span>
                    {opt}
                  </button>
                ))}
              </div>

              <button
                className="btn btn-primary w-full"
                onClick={handleAnswerSubmit}
                disabled={selectedOption === null}
              >
                {assessmentIndex + 1 < ASSESSMENT_QUESTIONS.length ? 'Next' : 'Finish'}
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 4: Results + Belt Reveal */}
        {step === 4 && placedBelt && (
          <motion.div
            key="results"
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.5 }}
            className="text-center"
            style={{ maxWidth: 400, width: '100%' }}
          >
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', duration: 1 }}
              style={{ fontSize: 80, marginBottom: 16 }}
            >
              {placedBelt.current.icon}
            </motion.div>

            <motion.h2
              className="heading-retro"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
            >
              {placedBelt.current.name}
            </motion.h2>

            <motion.p
              style={{ color: 'var(--text-secondary)', marginBottom: 8 }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.7 }}
            >
              Welcome to the Dojo, <span style={{ color: 'var(--gold)' }}>{name}</span>!
            </motion.p>

            {assessmentScore > 0 && (
              <motion.p
                style={{ color: 'var(--text-muted)', marginBottom: 24, fontSize: 13 }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.9 }}
              >
                Assessment: {assessmentScore}/{ASSESSMENT_QUESTIONS.length} correct
              </motion.p>
            )}

            {error && (
              <div style={{ color: 'var(--error)', marginBottom: 16, fontSize: 13 }}>{error}</div>
            )}

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.1 }}
            >
              <button
                className="btn btn-primary btn-lg w-full"
                onClick={handleFinish}
                disabled={creating}
                style={{
                  fontSize: 18,
                  letterSpacing: 2,
                  textTransform: 'uppercase',
                }}
              >
                {creating ? 'Setting up...' : 'Begin Training'}
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
