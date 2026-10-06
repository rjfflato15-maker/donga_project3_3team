import React, { useState } from 'react';
import { ShieldCheck, Mail, Lock, LogIn, AlertCircle, RefreshCw } from 'lucide-react';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [capsLock, setCapsLock] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password.trim()) {
      setError('이메일과 비밀번호를 입력해 주세요.');
      return;
    }

    try {
      setLoading(true);
      const res = await authApi.login({
        email: email.trim(),
        password,
      });

      if (res.success && res.user) {
        login(res.user, '');
      } else {
        throw new Error('로그인 정보를 확인하지 못했습니다. 다시 시도하세요.');
      }
    } catch (err: any) {
      setError(err.message || '로그인 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="cp-auth">
      {/* Dynamic Background Glow Elements */}

      {/* Main Card */}
      <div className="cp-login-card">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="cp-login-icon">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">증빙검수</h1>
          <p className="text-xs font-bold text-indigo-600 tracking-widest uppercase mt-0.5">
            계약 증빙 관리
          </p>
          <p className="text-xs font-semibold text-slate-500 mt-2">
            계약 증빙서류 누락·불일치 자동 검수 시스템
          </p>
        </div>

        {/* Quick Demo Info Box */}
        <div className="mb-6 bg-indigo-50/80 border border-indigo-100 rounded-2xl p-3.5 text-xs text-indigo-900">
          <div className="flex items-center space-x-1.5 font-bold mb-1">
            <span>사내 계정으로 접속</span>
          </div>
          <p className="text-[11px] text-indigo-700/90 font-medium">
            대표 또는 운영 담당자에게 받은 계정을 사용하세요. 초기 비밀번호는 첫 로그인 후 변경합니다.
          </p>
        </div>

        {/* Notification */}
        {error && (
          <div className="mb-6 bg-rose-50 border border-rose-200 rounded-2xl p-3.5 flex items-start space-x-2.5 text-rose-800 text-xs font-semibold">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
              이메일 주소
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
              <input
                type="email"
                id="login-email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@company.local"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                required
              />
            </div>
          </div>

          <div>
            <label htmlFor="login-password" className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
              비밀번호
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
              <input
                type="password"
                id="login-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => setCapsLock(e.getModifierState('CapsLock'))}
                onKeyUp={(e) => setCapsLock(e.getModifierState('CapsLock'))}
                onBlur={() => setCapsLock(false)}
                autoComplete="current-password"
                aria-describedby={capsLock ? 'login-caps-lock' : undefined}
                placeholder="••••••••"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                required
              />
            </div>
            {capsLock && <p id="login-caps-lock" role="status" aria-live="polite" className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-amber-700"><AlertCircle size={14} />Caps Lock이 켜져 있습니다.</p>}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="cp-button cp-primary w-full mt-2"
          >
            {loading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                <span>로그인하기</span>
              </>
            )}
          </button>
        </form>

        <p className="mt-8 text-center text-[11px] font-semibold text-slate-400">
          회사 계정으로 로그인
        </p>
      </div>
    </div>
  );
};
