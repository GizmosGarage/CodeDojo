import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useApi } from '../hooks/useApi';
import { useUser } from '../context/UserContext';
import SenseiMessage from './SenseiMessage';

function renderQuestionText(text) {
  if (!text) return null;
  const parts = text.split(/(`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} style={{
          background: 'rgba(255, 215, 0, 0.1)',
          padding: '2px 6px',
          borderRadius: 4,
          fontFamily: 'var(--font-mono, monospace)',
          color: 'var(--gold)',
          fontSize: '0.9em',
        }}>
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function Quiz({ skillId, difficulty, onComplete }) {
  const api = useApi();
  const { refreshUser } = useUser();
  const [quiz, setQuiz] = useState(null);
  const [selectedOption, setSelectedOption] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState(null);
  const [xpGained, setXpGained] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchQuiz = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedOption(null);
    setSubmitted(false);
    setResult(null);
    setXpGained(0);
    try {
      const data = await api.post('/quiz/generate', {
        skill_id: skillId || 'python_basics',
        difficulty: difficulty || 'beginner',
        count: 1,
      });
      const questions = data.questions || [];
      setQuiz(questions.length > 0 ? questions[0] : null);
    } catch (err) {
      setError('Failed to load quiz question. Try again.');
    } finally {
      setLoading(false);
    }
  }, [api, skillId, difficulty]);

  useEffect(() => {
    fetchQuiz();
  }, [fetchQuiz]);

  const handleSubmit = async () => {
    if (selectedOption === null || submitted) return;
    setSubmitted(true);
    const isCorrect = selectedOption === quiz.correct_answer;
    const xpAmount = isCorrect ? 15 : 0;
    const localResult = {
      correct: isCorrect,
      explanation: quiz.explanation || '',
      xp_earned: xpAmount,
    };
    setResult(localResult);
    setXpGained(xpAmount);
    if (xpAmount > 0) {
      try {
        await api.post('/xp/award', {
          amount: xpAmount,
          reason: 'quiz',
          skill_id: skillId || 'python_basics',
          correct: isCorrect,
        });
        refreshUser();
      } catch {
        // XP award failed silently
      }
    }
  };

  const handleContinue = () => {
    if (onComplete) {
      onComplete({
        correct: result?.correct || false,
        xp_earned: xpGained,
      });
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
        <button className="btn btn-primary" onClick={fetchQuiz}>Try Again</button>
      </div>
    );
  }

  if (!quiz) return null;

  const options = quiz.options || [];
  const correctAnswer = quiz.correct_answer;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="card">
        <div style={{ marginBottom: 8 }}>
          {quiz.skill && (
            <span className={`badge badge-${(difficulty || 'easy').toLowerCase()}`} style={{ marginRight: 8 }}>
              {difficulty || 'Beginner'}
            </span>
          )}
          {quiz.skill && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{quiz.skill}</span>
          )}
        </div>

        <h2 style={{ fontSize: 18, fontWeight: 600, lineHeight: 1.5, marginBottom: 4 }}>
          {renderQuestionText(quiz.question)}
        </h2>

        <div className="quiz-options">
          {options.map((option, idx) => {
            let className = 'quiz-option';
            if (submitted) {
              if (idx === correctAnswer) {
                className += ' correct';
              } else if (idx === selectedOption && idx !== correctAnswer) {
                className += ' incorrect';
              }
            } else if (idx === selectedOption) {
              className += ' selected';
            }

            return (
              <motion.button
                key={idx}
                className={className}
                onClick={() => !submitted && setSelectedOption(idx)}
                whileHover={!submitted ? { scale: 1.02 } : {}}
                whileTap={!submitted ? { scale: 0.98 } : {}}
                disabled={submitted}
              >
                <span style={{
                  display: 'inline-block',
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  border: '2px solid currentColor',
                  textAlign: 'center',
                  lineHeight: '20px',
                  fontSize: 12,
                  marginRight: 10,
                  flexShrink: 0,
                  opacity: 0.6,
                }}>
                  {String.fromCharCode(65 + idx)}
                </span>
                {renderQuestionText(option)}
              </motion.button>
            );
          })}
        </div>

        {!submitted && (
          <button
            className="btn btn-primary w-full"
            onClick={handleSubmit}
            disabled={selectedOption === null}
          >
            Submit Answer
          </button>
        )}

        <AnimatePresence>
          {submitted && result && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <div style={{
                textAlign: 'center',
                margin: '20px 0',
                fontSize: 20,
                fontWeight: 700,
                color: result.correct ? 'var(--success)' : 'var(--error)',
              }}>
                {result.correct ? 'Correct!' : 'Incorrect'}
              </div>

              {xpGained > 0 && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.5, y: 0 }}
                  animate={{ opacity: 1, scale: 1, y: -10 }}
                  transition={{ duration: 0.5, type: 'spring' }}
                  style={{
                    textAlign: 'center',
                    color: 'var(--gold)',
                    fontWeight: 700,
                    fontSize: 18,
                    marginBottom: 12,
                  }}
                >
                  +{xpGained} XP
                </motion.div>
              )}

              {(result.explanation || result.sensei_feedback) && (
                <SenseiMessage message={result.explanation || result.sensei_feedback} />
              )}

              <div className="mt-md">
                <button className="btn btn-primary w-full" onClick={handleContinue}>
                  Continue
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
