import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { useApi } from '../hooks/useApi';
import { useUser } from '../context/UserContext';

export default function Chat() {
  const api = useApi();
  const { beltInfo } = useUser();
  const [messages, setMessages] = useState([
    {
      role: 'sensei',
      content: 'Welcome to the Dojo, student. Ask me anything about Python, programming concepts, or your training.',
    },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);

    try {
      const data = await api.post('/chat', { message: text });
      const senseiMsg = {
        role: 'sensei',
        content: data.response || data.message || 'I sense a disturbance. Please try again.',
      };
      setMessages((prev) => [...prev, senseiMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'sensei', content: 'My apologies, student. I could not process your message. Please try again.' },
      ]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-container">
      <h1 className="heading-retro" style={{ marginBottom: 0 }}>Sensei Chat</h1>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            className={`chat-bubble ${msg.role}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <div className="chat-avatar">
              {msg.role === 'sensei' ? '\ud83e\udd4b' : beltInfo.current.icon}
            </div>
            <div className="chat-content">
              {msg.content}
            </div>
          </motion.div>
        ))}

        {sending && (
          <motion.div
            className="chat-bubble sensei"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <div className="chat-avatar">{'\ud83e\udd4b'}</div>
            <div className="chat-content">
              <div className="typing-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <input
          ref={inputRef}
          className="chat-input"
          placeholder="Ask Sensei a question..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button
          className="btn btn-primary"
          onClick={handleSend}
          disabled={sending || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
