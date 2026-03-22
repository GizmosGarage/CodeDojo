import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Editor from '@monaco-editor/react';
import { useApi } from '../hooks/useApi';
import { useUser } from '../context/UserContext';
import SenseiMessage from './SenseiMessage';

export default function CodeReview() {
  const api = useApi();
  const { refreshUser } = useUser();
  const [context, setContext] = useState('');
  const [code, setCode] = useState('');
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    setReview(null);
    try {
      const data = await api.post('/review', {
        code,
        context: context || 'General Python code',
      });
      setReview(data);
      if (data.xp_earned) refreshUser();
    } catch (err) {
      setError('Failed to get review. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setReview(null);
    setCode('');
    setContext('');
    setError(null);
  };

  const scoreColor = (score) => {
    if (score >= 8) return 'var(--success)';
    if (score >= 5) return 'var(--warning)';
    return 'var(--error)';
  };

  return (
    <div>
      <h1 className="heading-retro">Code Review</h1>

      {!review ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <SenseiMessage message="Paste your code below, student. I will review it and provide guidance on your path to mastery." />

          <div className="mt-lg mb-md">
            <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
              What does this code do? (optional context)
            </label>
            <input
              className="input"
              placeholder="e.g., A function that sorts a list using merge sort"
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
          </div>

          <div className="mb-md">
            <label style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'block', marginBottom: 6 }}>
              Your Code
            </label>
            <div className="editor-container" style={{ height: 350 }}>
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

          {error && (
            <div style={{ color: 'var(--error)', marginBottom: 12, fontSize: 13 }}>{error}</div>
          )}

          <button
            className="btn btn-primary btn-lg w-full"
            onClick={handleSubmit}
            disabled={loading || !code.trim()}
          >
            {loading ? (
              <span className="flex items-center gap-sm">
                <div className="loading-spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                Sensei is reviewing...
              </span>
            ) : (
              'Submit for Review'
            )}
          </button>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {/* Score Gauge */}
          <div className="card text-center mb-lg">
            <div
              className="score-gauge"
              style={{
                background: `conic-gradient(${scoreColor(review.score)} ${(review.score / 10) * 360}deg, var(--bg-panel) 0deg)`,
              }}
            >
              <span style={{ color: scoreColor(review.score) }}>{review.score}</span>
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: scoreColor(review.score) }}>
              {review.score >= 8 ? 'Excellent!' : review.score >= 5 ? 'Good Progress' : 'Needs Work'}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
              Score: {review.score}/10
            </div>
          </div>

          {/* Strengths */}
          {review.strengths && review.strengths.length > 0 && (
            <div className="card mb-md">
              <div className="card-title" style={{ color: 'var(--success)' }}>
                {'\u2705'} Strengths
              </div>
              <ul className="review-list review-strengths">
                {review.strengths.map((s, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                  >
                    {s}
                  </motion.li>
                ))}
              </ul>
            </div>
          )}

          {/* Improvements */}
          {review.improvements && review.improvements.length > 0 && (
            <div className="card mb-md">
              <div className="card-title" style={{ color: 'var(--orange)' }}>
                {'\ud83d\udfe0'} Areas for Improvement
              </div>
              <ul className="review-list review-improvements">
                {review.improvements.map((s, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 + 0.3 }}
                  >
                    {s}
                  </motion.li>
                ))}
              </ul>
            </div>
          )}

          {/* Sensei Feedback */}
          {review.feedback && (
            <SenseiMessage message={review.feedback} typing />
          )}

          {/* XP Earned */}
          {review.xp_earned > 0 && (
            <motion.div
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.5, type: 'spring' }}
              className="text-center mt-md"
              style={{ color: 'var(--gold)', fontWeight: 700, fontSize: 20 }}
            >
              +{review.xp_earned} XP
            </motion.div>
          )}

          <div className="mt-lg">
            <button className="btn btn-secondary w-full" onClick={handleReset}>
              Review Another
            </button>
          </div>
        </motion.div>
      )}
    </div>
  );
}
