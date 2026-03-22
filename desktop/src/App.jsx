import React from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { UserProvider, useUser } from './context/UserContext';
import TitleBar from './components/TitleBar';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Training from './components/Training';
import Quiz from './components/Quiz';
import Challenge from './components/Challenge';
import SkillTree from './components/SkillTree';
import Profile from './components/Profile';
import BeltExam from './components/BeltExam';
import Onboarding from './components/Onboarding';

function AppContent() {
  const { user, loading } = useUser();
  const location = useLocation();

  if (loading) {
    return (
      <>
        <TitleBar />
        <div className="app-layout">
          <div className="main-content flex items-center justify-center">
            <div className="loading-spinner" />
          </div>
        </div>
      </>
    );
  }

  const isOnboarding = location.pathname === '/onboarding';
  const needsOnboarding = !user && !isOnboarding;

  if (needsOnboarding) {
    return (
      <>
        <TitleBar />
        <div className="app-layout">
          <div className="main-content" style={{ padding: 0 }}>
            <Navigate to="/onboarding" replace />
          </div>
        </div>
      </>
    );
  }

  if (isOnboarding) {
    return (
      <>
        <TitleBar />
        <div className="app-layout">
          <div className="main-content" style={{ padding: 0 }}>
            <Routes>
              <Route path="/onboarding" element={<Onboarding />} />
            </Routes>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TitleBar />
      <div className="app-layout">
        <Sidebar />
        <div className="main-content">
          <Routes>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/train" element={<Training />} />
            <Route path="/quiz" element={<Quiz />} />
            <Route path="/challenge" element={<Challenge />} />
            <Route path="/skills" element={<SkillTree />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/belt-exam" element={<BeltExam />} />
            <Route path="/onboarding" element={<Onboarding />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </div>
      </div>
    </>
  );
}

export default function App() {
  return (
    <UserProvider>
      <AppContent />
    </UserProvider>
  );
}
