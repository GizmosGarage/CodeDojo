import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useApi } from '../hooks/useApi';

const BELT_CONFIG = [
  { name: 'White Belt', icon: '\u2b1c', rank: 0, color: '#e0e0e0' },
  { name: 'Yellow Belt', icon: '\ud83d\udfe1', rank: 1, color: '#ffd700' },
  { name: 'Orange Belt', icon: '\ud83d\udfe0', rank: 2, color: '#ff6b35' },
  { name: 'Green Belt', icon: '\ud83d\udfe2', rank: 3, color: '#00c853' },
  { name: 'Blue Belt', icon: '\ud83d\udfe5', rank: 4, color: '#2979ff' },
  { name: 'Purple Belt', icon: '\ud83d\udfe3', rank: 5, color: '#9c27b0' },
  { name: 'Brown Belt', icon: '\ud83d\udfe4', rank: 6, color: '#795548' },
  { name: 'Black Belt', icon: '\u2b1b', rank: 7, color: '#212121' },
];

function getBeltByRank(rank) {
  if (rank >= 0 && rank < BELT_CONFIG.length) {
    return BELT_CONFIG[rank];
  }
  return BELT_CONFIG[0];
}

function getLevelInfo(totalXp, currentLevel) {
  // Steep curve: Level N requires 25 * N^2 cumulative XP
  const xpForCurrent = 25 * (currentLevel * currentLevel);
  const xpForNext = 25 * ((currentLevel + 1) * (currentLevel + 1));
  const xpInLevel = totalXp - xpForCurrent;
  const xpNeeded = xpForNext - xpForCurrent;
  const progress = xpNeeded > 0 ? Math.min(xpInLevel / xpNeeded, 1) : 1;

  return { level: currentLevel, xpInLevel, xpNeeded, progress, xpForNext };
}

// Keep backward compat export
function getBeltInfo(xp) {
  // Fallback — in new system, belt is rank-based
  return {
    current: BELT_CONFIG[0],
    next: BELT_CONFIG[1],
    xpInBelt: xp,
    xpNeeded: 100,
    progress: Math.min(xp / 100, 1),
  };
}

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);
  const [userLoading, setUserLoading] = useState(true);
  const api = useApi();

  const refreshUser = useCallback(async () => {
    setUserLoading(true);
    try {
      const profile = await api.get('/user');
      setUser(profile);
    } catch {
      setUser(null);
    } finally {
      setUserLoading(false);
    }
  }, [api]);

  useEffect(() => {
    refreshUser();
  }, []);

  const beltRank = user?.belt_rank || 0;
  const currentBelt = getBeltByRank(beltRank);
  const nextBelt = beltRank + 1 < BELT_CONFIG.length ? BELT_CONFIG[beltRank + 1] : null;
  const level = user?.level || 1;
  const levelInfo = getLevelInfo(user?.total_xp || 0, level);

  const beltInfo = {
    current: currentBelt,
    next: nextBelt,
    // Legacy compat
    xpInBelt: 0,
    xpNeeded: 0,
    progress: 0,
  };

  return (
    <UserContext.Provider value={{
      user, refreshUser, beltInfo, levelInfo,
      loading: userLoading, BELT_CONFIG,
    }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error('useUser must be used within UserProvider');
  return ctx;
}

export { BELT_CONFIG, getBeltInfo, getBeltByRank, getLevelInfo };
