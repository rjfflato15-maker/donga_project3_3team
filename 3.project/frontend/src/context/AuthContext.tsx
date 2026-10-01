import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types/auth';
import { authApi } from '../api/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  restoring: boolean;
  updateUser: (user: User) => void;
  login: (user: User, token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // 사이트를 다시 열거나 새로 진입 시 항상 로그인 화면이 나오도록 메모리 세션 상태(초기값 null)로 관리
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(true);
  useEffect(() => {
    let active = true;
    authApi.me().then(value => { if (active) setUser(value); }).catch(() => {}).finally(() => { if (active) setRestoring(false); });
    const expired = () => { setUser(null); setToken(null); };
    window.addEventListener('session-expired', expired);
    return () => { active = false; window.removeEventListener('session-expired', expired); };
  }, []);

  const login = (newUser: User, newToken: string) => {
    setUser(newUser);
    setToken(newToken);
  };

  const logout = () => {
    void authApi.logout().catch(() => {});
    setUser(null);
    setToken(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        restoring,
        updateUser: setUser,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
