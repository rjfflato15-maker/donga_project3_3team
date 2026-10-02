import React, { useEffect, useState } from 'react';
import { Download, KeyRound, Save, ShieldCheck, Users } from 'lucide-react';
import { api, downloadProtected } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { PilotInfo, PilotMetrics } from '../types';
import { PilotPasswordChange } from './PilotPasswordChange';
import { CompanyPolicySection } from './review/CompanyPolicySection';

type TeamUser = Awaited<ReturnType<typeof api.users>>[number];
const field = 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm';
const button = 'rounded-lg bg-indigo-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50';

export const PilotOperations: React.FC<{ info: PilotInfo; onChanged: () => Promise<void> }> = ({ info, onChanged }) => {
  const { user } = useAuth();
  const representative = user?.role === 'representative' || user?.role === 'admin';
  const [name, setName] = useState(info.company_name);
  const [users, setUsers] = useState<TeamUser[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [newUser, setNewUser] = useState({ email: '', display_name: '', role: 'operator', temporary_password: '' });
  const [resetId, setResetId] = useState<number | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [metrics, setMetrics] = useState<PilotMetrics | null>(null);
  const [metricsError, setMetricsError] = useState('');
  useEffect(() => {
    let active = true;
    api.pilotMetrics().then(value => { if (active) { setMetrics(value); setMetricsError(''); } })
      .catch(reason => { if (active) setMetricsError(reason.message); });
    return () => { active = false; };
  }, [info]);
  useEffect(() => { setName(info.company_name); }, [info]);
  useEffect(() => {
    if (!representative) return;
    let active = true;
    api.users().then(value => { if (active) setUsers(value); }).catch(reason => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, [representative]);
  const act = async (operation: () => Promise<void>, message: string) => {
    setBusy(true); setError(''); setNotice('');
    try { await operation(); setNotice(message); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '처리하지 못했습니다.'); }
    finally { setBusy(false); }
  };
  if (passwordOpen) return <PilotPasswordChange onDone={() => setPasswordOpen(false)} />;
  return <div className="mx-auto max-w-5xl space-y-6 p-5 lg:p-8">
    <div><h1 className="text-2xl font-bold text-slate-900">업무 설정 · 계정</h1><p className="mt-2 text-sm text-slate-600">공용 PC에 자료를 보관하고, 각자 계정으로 접속합니다.</p></div>
    {error && <p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    {notice && <p role="status" className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p>}
    <section className="rounded-2xl border border-slate-200 bg-white p-6">
      <h2 className="flex items-center gap-2 font-bold"><ShieldCheck size={20} />현재 실행 환경</h2>
      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div className="rounded-lg bg-slate-50 p-3">DB <strong className="block">{info.local_database ? '공용 PC의 SQLite' : '외부 DB'}</strong></div>
        <div className="rounded-lg bg-slate-50 p-3">국세청 <strong className="block">{info.nts_mode === 'disabled' ? '미연동 · 외부 요청 안 함' : info.nts_mode === 'demo' ? '데모 데이터' : '사업자 상태 조회 모드'}</strong></div>
        <div className="rounded-lg bg-slate-50 p-3">LLM <strong className="block">{info.llm_connected ? '연결됨' : '연결 없음 · 규칙 기반 검수'}</strong></div>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-600">새로 등록한 원본은 공용 PC에 저장됩니다. 다른 직원은 파일을 따로 받지 않아도 이 앱에서 열거나 내려받을 수 있습니다. PC를 끄면 접속할 수 없습니다.</p>
      <button className="mt-4 flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm" onClick={() => setPasswordOpen(true)}><KeyRound size={16} />내 비밀번호 변경</button>
    </section>
    <section className="rounded-2xl border border-slate-200 bg-white p-6">
      <h2 className="font-bold">시범 업무 측정</h2>
      <p className="mt-2 text-sm text-slate-600">현재 업무 목록의 기록을 집계합니다. 첫 원본 등록 완료부터 첫 대표 확인까지의 경과시간이며, 대기시간이 포함됩니다.</p>
      {metricsError && <p role="alert" className="mt-3 text-sm text-rose-700">{metricsError}</p>}
      {metrics && <>
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
          <div className="rounded-lg bg-slate-50 p-3">대표 확인 대기<strong className="block">{metrics.awaiting_confirmation_count} / {metrics.contract_count}건</strong></div>
          <div className="rounded-lg bg-slate-50 p-3">현재 확인 완료<strong className="block">{metrics.confirmed_count}건</strong></div>
          <div className="rounded-lg bg-slate-50 p-3">평균 등록→첫 확인<strong className="block">{metrics.mean_elapsed_seconds == null ? '확인 기록 없음' : `${metrics.mean_elapsed_seconds < 60 ? '1분 미만' : Math.round(metrics.mean_elapsed_seconds / 60) + '분'} · ${metrics.timed_contract_count}건`}</strong></div>
        </div>
        <p className="mt-3 text-xs text-slate-500">원본 {metrics.document_registration_count}건 · 추출값 보정 기록 {metrics.field_correction_count}건. {metrics.limitation}</p>
      </>}
    </section>
    <section className="rounded-2xl border border-slate-200 bg-white p-6">
      <h2 className="font-bold">회사 이름</h2>
      <label className="mt-3 block text-sm">화면과 백업 파일에 표시되는 이름<input disabled={!representative || busy} className={field + ' mt-1'} value={name} maxLength={80} onChange={e => setName(e.target.value)} /></label>
      {representative && <button className={button + ' mt-4 flex items-center gap-2'} disabled={busy || !name.trim() || name.trim() === info.company_name} onClick={() => void act(async () => { await api.savePilotSettings(name.trim(), info.required_document_types); await onChanged(); }, '회사 이름을 저장했습니다.')}><Save size={16} />이름 저장</button>}
    </section>
    <CompanyPolicySection canEdit={representative} onSaved={onChanged} />
    {representative && <>
      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <h2 className="flex items-center gap-2 font-bold"><Users size={20} />사용자 관리</h2>
        <p className="mt-1 text-sm text-slate-600">담당자는 등록·수정, 대표는 조회·최종 확인·계정 관리를 담당합니다. 임시 비밀번호는 처음 로그인할 때 변경해야 합니다.</p>
        <div className="mt-4 space-y-3">{users.map(member => <div key={member.user_id} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 p-3 text-sm">
          <div className="min-w-48 flex-1"><strong>{member.display_name}</strong><span className="ml-2 text-slate-500">{member.role === 'representative' ? '대표' : member.role === 'admin' ? '관리자' : '담당자'}</span><p className="mt-1 text-slate-500">{member.email}</p></div>
          <span className={member.active ? 'text-emerald-700' : 'text-slate-500'}>{member.active ? '사용 중' : '중지됨'}</span>
          {member.must_change_password && <span className="text-amber-700">초기 비밀번호 변경 필요</span>}
          {member.user_id !== user?.user_id && <><button disabled={busy} className="rounded-lg border px-3 py-2" onClick={() => void act(async () => { await api.setUserActive(member.user_id, !member.active); setUsers(await api.users()); }, '계정 사용 상태를 변경했습니다. 기존 로그인은 종료됩니다.')}>{member.active ? '사용 중지' : '사용 재개'}</button><button disabled={busy} className="rounded-lg border px-3 py-2" onClick={() => { setResetId(member.user_id); setResetPassword(''); }}>비밀번호 재설정</button></>}
        </div>)}</div>
        {resetId !== null && <form className="mt-4 flex flex-wrap gap-3 rounded-xl bg-amber-50 p-4" onSubmit={e => { e.preventDefault(); void act(async () => { await api.resetPassword(resetId, resetPassword); setResetPassword(''); setResetId(null); setUsers(await api.users()); }, '임시 비밀번호를 설정했습니다. 본인에게 안전하게 전달하세요.'); }}>
          <label className="min-w-56 flex-1 text-sm">새 임시 비밀번호<input className={field + ' mt-1'} type="password" minLength={12} maxLength={128} required autoComplete="new-password" value={resetPassword} onChange={e => setResetPassword(e.target.value)} /></label>
          <button disabled={busy} className={button}>재설정</button><button type="button" className="text-sm" onClick={() => setResetId(null)}>취소</button>
        </form>}
        <form className="mt-6 grid gap-3 border-t border-slate-200 pt-5 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); void act(async () => { await api.addUser(newUser); setNewUser({ email: '', display_name: '', role: 'operator', temporary_password: '' }); setUsers(await api.users()); }, '계정을 추가했습니다. 임시 비밀번호를 본인에게 안전하게 전달하세요.'); }}>
          <label className="text-sm">이름<input className={field + ' mt-1'} required maxLength={80} value={newUser.display_name} onChange={e => setNewUser(old => ({ ...old, display_name: e.target.value }))} /></label>
          <label className="text-sm">로그인 주소<input className={field + ' mt-1'} type="email" required value={newUser.email} onChange={e => setNewUser(old => ({ ...old, email: e.target.value }))} placeholder="member@company.local" /></label>
          <label className="text-sm">권한<select className={field + ' mt-1'} value={newUser.role} onChange={e => setNewUser(old => ({ ...old, role: e.target.value }))}><option value="operator">담당자</option><option value="representative">대표</option></select></label>
          <label className="text-sm">임시 비밀번호 · 12자 이상<input className={field + ' mt-1'} type="password" minLength={12} maxLength={128} required autoComplete="new-password" value={newUser.temporary_password} onChange={e => setNewUser(old => ({ ...old, temporary_password: e.target.value }))} /></label>
          <button disabled={busy} className={button}>계정 추가</button>
        </form>
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <h2 className="font-bold">DB · 원본 함께 백업</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">계약 DB와 원본, 추출 텍스트를 한 ZIP으로 내려받습니다. 백업에는 민감한 원문과 계정 정보가 들어 있습니다. 암호화되지 않은 ZIP이므로 회사에서 허용한 보호 저장소에 보관하세요. 초기 계정 안내 파일은 포함하지 않습니다.</p>
        <button disabled={busy} className={button + ' mt-4 flex items-center gap-2'} onClick={() => void act(() => downloadProtected('/api/pilot/backup', 'C업체_업무백업.zip'), '백업 다운로드를 요청했습니다. 저장된 파일을 확인하세요.')}><Download size={16} />업무 백업 다운로드</button>
        <p className="mt-3 text-xs text-slate-500">복원은 서버를 멈춘 뒤 별도 복원 명령으로 새 저장소에 진행합니다. 주기적인 자동 백업과 실제 복원 검증은 시범 운영 전에 설정해야 합니다.</p>
      </section>
    </>}
  </div>;
};
