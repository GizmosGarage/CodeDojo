import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Editor from '@monaco-editor/react';
import { useApi } from '../hooks/useApi';
import { useUser } from '../context/UserContext';
import SenseiMessage from './SenseiMessage';

export default function Challenge({ skillId, difficulty, onComplete }) {
  const api = useApi();
  const { refreshUser } = useUser();
  const [challenge, setChallenge] = useState(null);
  const [code, setCode] = useState('');
  const [testResults, setTestResults] = useState([]);
  const [feedback, setFeedback] = useState('');
  const [attempt, setAttempt] = useState(1);
  const [maxAttempts] = useState(3);
  const [passed, setPassed] = useState(false);
  const [xpGained, setXpGained] = useState(0);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [hintsRevealed, setHintsRevealed] = useState(0);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  const fetchChallenge = useCallback(async () => {
    setLoading(true);
    setError(null);
    setTestResults([]);
    setFeedback('');
    setAttempt(1);
    setPassed(false);
    setXpGained(0);
    setHintsRevealed(0);
    setDone(false);
    try {
      const data = await api.post('/challenge/generate', {
        skill_id: skillId || 'python_basics',
        difficulty: difficulty || 'beginner',
      });
      setChallenge(data);
      setCode(data.starter_code || data.template || '# Write your solution here\n');
    } catch {
      setError('Failed to load challenge.');
    } finally {
      setLoading(false);
    }
  }, [api, skillId, difficulty]);

  useEffect(() => {
    fetchChallenge();
  }, [fetchChallenge]);

  const handleRunTests = async () => {
    if (running || done) return;
    setRunning(true);
    setFeedback('');
    try {
      // Run the tests
      const runData = await api.post('/challenge/run', {
        challenge,
        student_code: code,
      });

      const results = runData.results || [];
      setTestResults(results);

      const allPassed = runData.all_passed || false;

      // Get sensei evaluation
      let evalFeedback = '';
      try {
        const evalData = await api.post('/challenge/evaluate', {
          title: challenge.title || 'Challenge',
          code,
          results,
          all_passed: allPassed,
        });
        evalFeedback = evalData.feedback || '';
        setFeedback(evalFeedback);
      } catch {
        setFeedback('');
      }

      if (allPassed) {
        setPassed(true);
        setDone(true);
        // Award XP
        try {
          await api.post('/xp/award', {
            amount: 25,
            reason: 'challenge',
            skill_id: skillId || 'python_basics',
            correct: true,
          });
          setXpGained(25);
          refreshUser();
        } catch {
          setXpGained(0);
        }
      }

      if (!allPassed && attempt >= maxAttempts) {
        setDone(true);
        if (!evalFeedback) setFeedback('You have used all attempts. Review the solution and try again next time.');
      }

      if (!allPassed && attempt < maxAttempts) {
        setAttempt((prev) => prev + 1);
      }
    } catch {
      setFeedback('Error running tests. Please try again.');
    } finally {
      setRunning(false);
    }
  };

  const handleContinue = () => {
    if (onComplete) {
      onComplete({ passed, xp_earned: xpGained });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ padding: 60 }}>
        <div className="loading-spinner" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card text-center" style={{ padding: 40 }}>
        <p style={{ color: 'var(--error)', marginBottom: 16 }}>{error}</p>
        <button className="btn btn-primary" onClick={fetchChallenge}>Try Again</button>
      </div>
    );
  }

  if (!challenge) return null;

  const hints = challenge.hints || [];
  const tests = challenge.test_cases || challenge.tests || [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{ height: 'calc(100vh - 140px)' }}
    >
      <div className="split-pane">
        {/* Left Pane - Description */}
        <div className="split-left">
          <div className="flex items-center gap-sm mb-md">
            <h2 style={{ fontSize: 18, fontWeight: 700 }}>
              {challenge.title || 'Challenge'}
            </h2>
            <span className={`badge badge-${(difficulty || 'easy').toLowerCase()}`}>
              {difficulty || 'Beginner'}
            </span>
          </div>

          <div style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-primary)', marginBottom: 20 }}>
            {challenge.description}
          </div>

          {tests.length > 0 && (
            <div className="mb-md">
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                Test Cases
              </h3>
              {tests.map((test, i) => (
                <div key={i} style={{
                  padding: '8px 12px',
                  background: 'var(--bg-deep)',
                  borderRadius: 6,
                  marginBottom: 6,
                  fontSize: 13,
                  fontFamily: 'monospace',
                }}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>
                    {test.description || `Test ${i + 1}`}
                  </div>
                  {test.input && (
                    <div>Input: <code style={{ color: 'var(--gold)' }}>{test.input}</code></div>
                  )}
                  {test.expected && (
                    <div>Expected: <code style={{ color: 'var(--success)' }}>{test.expected}</code></div>
                  )}
                </div>
              ))}
            </div>
          )}

          {hints.length > 0 && (
            <div className="mb-md">
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                Hints
              </h3>
              {hints.map((hint, i) => (
                <div key={i} style={{ marginBottom: 6 }}>
                  {i < hintsRevealed ? (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      style={{
                        padding: '8px 12px',
                        background: 'rgba(255, 145, 0, 0.08)',
                        borderRadius: 6,
                        fontSize: 13,
                        color: 'var(--warning)',
                        borderLeft: '3px solid var(--warning)',
                      }}
                    >
                      {hint}
                    </motion.div>
                  ) : (
                    <button
                      className="hint-btn"
                      onClick={() => setHintsRevealed(i + 1)}
                      disabled={i > hintsRevealed}
                    >
                      Reveal Hint {i + 1}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Pane - Editor + Results */}
        <div className="split-right">
          <div className="split-right-top">
            <div className="editor-container" style={{ height: '100%' }}>
              <Editor
                height="100%"
                language="python"
                theme="vs-dark"
                value={code}
                onChange={(value) => setCode(value || '')}
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  lineNumbers: 'on',
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  tabSize: 4,
                  wordWrap: 'on',
                  padding: { top: 8 },
                }}
              />
            </div>
          </div>

          <div className="split-right-bottom">
            <div className="flex items-center justify-between mb-sm">
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>
                Test Results
              </h3>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Attempt {Math.min(attempt, maxAttempts)}/{maxAttempts}
              </span>
            </div>

            {testResults.length === 0 && !running && (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '8px 0' }}>
                Run tests to see results...
              </div>
            )}

            {testResults.map((result, i) => (
              <motion.div
                key={i}
                className="test-result"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.1 }}
              >
                <span className={result.passed || result.pass ? 'test-pass' : 'test-fail'}>
                  {result.passed || result.pass ? '\u2705' : '\u274c'}
                </span>
                <span>{result.description || result.name || `Test ${i + 1}`}</span>
                {result.error && (
                  <span style={{ fontSize: 11, color: 'var(--error)', marginLeft: 8 }}>
                    {result.error}
                  </span>
                )}
              </motion.div>
            ))}

            {feedback && <SenseiMessage message={feedback} />}

            <AnimatePresence>
              {xpGained > 0 && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  style={{
                    textAlign: 'center',
                    color: 'var(--gold)',
                    fontWeight: 700,
                    fontSize: 18,
                    margin: '12px 0',
                  }}
                >
                  +{xpGained} XP
                </motion.div>
              )}
            </AnimatePresence>

            <div className="flex gap-sm mt-sm">
              {!done ? (
                <button
                  className="btn btn-primary"
                  onClick={handleRunTests}
                  disabled={running}
                  style={{ flex: 1 }}
                >
                  {running ? (
                    <>
                      <div className="loading-spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                      Running...
                    </>
                  ) : (
                    '\u25b6 Run Tests'
                  )}
                </button>
              ) : (
                <button className="btn btn-primary" onClick={handleContinue} style={{ flex: 1 }}>
                  Continue
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
