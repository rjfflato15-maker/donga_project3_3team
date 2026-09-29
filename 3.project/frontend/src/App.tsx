import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ContractDashboard } from './pages/ContractDashboard';
import { LoginPage } from './pages/LoginPage';

const AppContent: React.FC = () => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <ContractDashboard /> : <LoginPage />;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;

