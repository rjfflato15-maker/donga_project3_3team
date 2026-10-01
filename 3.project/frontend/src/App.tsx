import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ContractDashboard } from './pages/ContractDashboard';
import { LoginPage } from './pages/LoginPage';
import { PilotPasswordChange } from './components/PilotPasswordChange';

const AppContent: React.FC = () => {
  const { isAuthenticated, restoring, user } = useAuth();
  if (restoring) return <div className="p-10 text-center text-slate-600">로그인 상태 확인 중…</div>;
  if (!isAuthenticated) return <LoginPage />;
  if (user?.must_change_password) return <PilotPasswordChange initial />;
  return <ContractDashboard />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;

