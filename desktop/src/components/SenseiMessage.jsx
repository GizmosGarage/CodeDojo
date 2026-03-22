import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

export default function SenseiMessage({ message, typing = false }) {
  const [displayedText, setDisplayedText] = useState(typing ? '' : message);
  const [isTyping, setIsTyping] = useState(typing);

  useEffect(() => {
    if (!typing) {
      setDisplayedText(message);
      setIsTyping(false);
      return;
    }

    setDisplayedText('');
    setIsTyping(true);
    let index = 0;
    const interval = setInterval(() => {
      if (index < message.length) {
        setDisplayedText(message.slice(0, index + 1));
        index++;
      } else {
        clearInterval(interval);
        setIsTyping(false);
      }
    }, 20);

    return () => clearInterval(interval);
  }, [message, typing]);

  return (
    <motion.div
      className="sensei-message"
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="sensei-label">Sensei:</div>
      <div className="sensei-text">
        {displayedText}
        {isTyping && (
          <span style={{ opacity: 0.5, marginLeft: 2 }}>|</span>
        )}
      </div>
    </motion.div>
  );
}
