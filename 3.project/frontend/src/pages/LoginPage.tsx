import React, { useState } from 'react';
import { ShieldCheck, Mail, Lock, LogIn, AlertCircle, RefreshCw, Sparkles } from 'lucide-react';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('nj445325@gmail.com');
  const [password, setPassword] = useState('admin123!');
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

      if (res.user && res.token) {
        login(res.user, res.token);
      } else {
        login({ email: email.trim() }, 'mock_token');
      }
    } catch (err: any) {
      setError(err.message || '로그인 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Dynamic Background Glow Elements */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-indigo-600/30 rounded-full blur-3xl" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-purple-600/30 rounded-full blur-3xl" />

      {/* Main Card */}
      <div className="max-w-md w-full bg-white/95 backdrop-blur-2xl rounded-3xl p-8 shadow-2xl border border-white/20 relative z-10">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-blue-500 mx-auto flex items-center justify-center text-white shadow-xl shadow-indigo-500/30 mb-4 transition-transform hover:scale-105">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Smart Contract</h1>
          <p className="text-xs font-bold text-indigo-600 tracking-widest uppercase mt-0.5">
            EVIDENCE HUB
          </p>
          <p className="text-xs font-semibold text-slate-500 mt-2">
            계약 증빙서류 누락·불일치 자동 검수 시스템
          </p>
        </div>

        {/* Quick Demo Info Box */}
        <div className="mb-6 bg-indigo-50/80 border border-indigo-100 rounded-2xl p-3.5 text-xs text-indigo-900">
          <div className="flex items-center space-x-1.5 font-bold mb-1">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <span>데모 체험 계정 안내</span>
          </div>
          <p className="text-[11px] text-indigo-700/90 font-medium">
            아이디: <code className="font-extrabold bg-white px-1.5 py-0.5 rounded border border-indigo-200">nj445325@gmail.com</code><br />
            비밀번호: <code className="font-extrabold bg-white px-1.5 py-0.5 rounded border border-indigo-200 mt-1 inline-block">admin123!</code>
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
            <label className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
              이메일 주소
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
              비밀번호
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-extrabold py-3 px-4 rounded-xl text-sm shadow-lg shadow-indigo-500/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
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
          Smart Contract Evidence Hub • 3조 B2B 검수 시스템
        </p>
      </div>
    </div>
  );
};
