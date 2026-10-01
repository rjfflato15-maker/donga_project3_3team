import React, { useState } from 'react';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';

export const PilotPasswordChange: React.FC<{ initial?: boolean; onDone?: () => void }> = ({ initial, onDone }) => {
  const { updateUser, logout } = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (next !== repeat) { setError('새 비밀번호가 서로 다릅니다.'); return; }
    setBusy(true); setError('');
    try { updateUser(await authApi.changeOwnPassword(current, next)); onDone?.(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '변경하지 못했습니다.'); }
    finally { setBusy(false); }
  };
  return <div className={initial ? 'min-h-screen bg-slate-50 flex items-center justify-center p-6' : ''}>
    <form onSubmit={submit} className="bg-white border border-slate-200 rounded-2xl p-6 max-w-md w-full space-y-4">
      <h1 className="text-xl font-bold">{initial ? '초기 비밀번호 변경' : '비밀번호 변경'}</h1>
      <p className="text-sm text-slate-600">12자 이상으로 설정하세요. 사내망에서 외부 이메일 없이 변경합니다.</p>
      <label className="block text-sm">현재 비밀번호<input autoComplete="current-password" type="password" required value={current} onChange={e => setCurrent(e.target.value)} className="mt-1 w-full border rounded-lg p-2" /></label>
      <label className="block text-sm">새 비밀번호<input autoComplete="new-password" type="password" required minLength={12} maxLength={128} value={next} onChange={e => setNext(e.target.value)} className="mt-1 w-full border rounded-lg p-2" /></label>
      <label className="block text-sm">새 비밀번호 확인<input autoComplete="new-password" type="password" required minLength={12} value={repeat} onChange={e => setRepeat(e.target.value)} className="mt-1 w-full border rounded-lg p-2" /></label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="flex gap-3"><button disabled={busy} className="bg-indigo-600 text-white rounded-lg px-4 py-2 disabled:opacity-50">변경하고 계속하기</button><button type="button" onClick={logout} className="text-sm text-slate-600">로그아웃</button></div>
    </form>
  </div>;
};
