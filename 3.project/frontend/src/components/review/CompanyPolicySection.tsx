import React, { useEffect, useState } from 'react';
import { requestJson } from '../../api/client';
import { DocumentType } from '../../types';
import { DOCUMENT_TYPE_KO } from '../../utils/reviewSummary';
import { Building2, Save } from 'lucide-react';

type CompanyType = 'SOLE_PROPRIETOR' | 'SMALL_BUSINESS' | 'MID_SIZED';
type Role = 'operator' | 'representative';
interface Policy {
  company_type: CompanyType;
  required_document_types: DocumentType[];
  roles: Record<Role, string>;
  approval_steps: { role: Role; label: string }[];
}

const TYPE_INFO: Record<CompanyType, { title: string; who: string; flow: string }> = {
  SOLE_PROPRIETOR: { title: '개인사업자', who: '소수 인원이 자료 준비와 확인', flow: '담당자 준비·결재 요청 → 대표 공식 결재 1단계' },
  SMALL_BUSINESS: { title: '소기업', who: '담당자 1명 + 대표 (시범 C업체)', flow: '담당자 준비·결재 요청 → 대표 공식 결재 1단계' },
  MID_SIZED: { title: '중기업·중견', who: '담당자 여러 명, 결재 단계가 있음', flow: '담당자 검토 → 대표 최종 결재 (2단계)' },
};

const ALL_TYPES: DocumentType[] = ['contract', 'estimate', 'business_registration', 'bank_account', 'tax_invoice', 'inspection_confirmation'];
const json = (method: string, data: unknown): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });

interface Props {
  canEdit: boolean;
  onSaved: () => Promise<void>;
}

export const CompanyPolicySection: React.FC<Props> = ({ canEdit, onSaved }) => {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [saved, setSaved] = useState<Policy | null>(null);
  const [presets, setPresets] = useState<Policy[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([requestJson<Policy>('/api/pilot/company-policy'), requestJson<Policy[]>('/api/pilot/company-policy/presets')])
      .then(([p, list]) => { if (active) { setPolicy(p); setSaved(p); setPresets(list); } })
      .catch((e) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  if (!policy) return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">{error || '회사 설정을 불러오는 중…'}</section>
  );

  const dirty = JSON.stringify(policy) !== JSON.stringify(saved);
  const twoStep = policy.approval_steps.length === 2;
  const set = (patch: Partial<Policy>) => { setPolicy({ ...policy, ...patch }); setNotice(''); setConfirming(false); };

  const choosePreset = (type: CompanyType) => {
    const preset = presets.find((p) => p.company_type === type);
    // 회사가 고른 필수 서류는 유지하고, 유형별 역할 이름과 결재 단계만 기본값으로 바꾼다
    if (preset) set({ ...preset, required_document_types: policy.required_document_types });
    else set({ company_type: type });
  };
  const setTwoStep = (on: boolean) => set({
    approval_steps: on
      ? [{ role: 'operator', label: '담당 검토' }, { role: 'representative', label: '최종 결재' }]
      : [{ role: 'representative', label: '최종 확인' }],
  });

  const save = async () => {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await requestJson<Policy>('/api/pilot/company-policy', json('PUT', policy));
      setPolicy(result); setSaved(result); setConfirming(false);
      setNotice('저장했습니다. 모든 계약을 다시 검사했고, 이전 결재는 다시 확인이 필요합니다.');
      await onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장하지 못했습니다.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 space-y-5" aria-labelledby="policy-title">
      <div>
        <h2 id="policy-title" className="flex items-center gap-2 font-bold text-slate-900"><Building2 size={20} /> 회사 유형 · 검사 · 결재 설정</h2>
        <p className="mt-1 text-sm text-slate-600">회사마다 다른 부분은 코드를 고치지 않고 여기서 바꿉니다. {canEdit ? '' : '대표 계정만 바꿀 수 있습니다.'}</p>
      </div>

      <fieldset disabled={!canEdit || busy} className="space-y-5">
        <div>
          <legend className="mb-2 text-sm font-semibold text-slate-800">회사 유형</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {(Object.keys(TYPE_INFO) as CompanyType[]).map((t) => {
              const on = policy.company_type === t;
              return (
                <button type="button" key={t} onClick={() => choosePreset(t)} aria-pressed={on}
                  className={`rounded-xl border-2 p-3 text-left text-sm transition ${on ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:border-indigo-300'}`}>
                  <div className="font-bold text-slate-900">{TYPE_INFO[t].title}</div>
                  <div className="text-xs text-slate-500">{TYPE_INFO[t].who}</div>
                  <div className="mt-1 text-xs text-indigo-700">{TYPE_INFO[t].flow}</div>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-slate-500">회사 유형은 결재 단계와 이름의 기본값을 정할 뿐입니다. 법적 기업 규모는 업종별 매출 기준이 있어 따로 확인이 필요합니다.</p>
        </div>

        <div>
          <div className="mb-2 text-sm font-semibold text-slate-800">필수 서류</div>
          <div className="grid gap-2 sm:grid-cols-3">
            {ALL_TYPES.map((t) => (
              <label key={t} className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={policy.required_document_types.includes(t)}
                  onChange={(e) => set({ required_document_types: e.target.checked ? [...policy.required_document_types, t] : policy.required_document_types.filter((x) => x !== t) })} />
                {DOCUMENT_TYPE_KO[t]}
              </label>
            ))}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <div className="mb-2 text-sm font-semibold text-slate-800">역할 이름</div>
            <div className="grid gap-2">
              {(['operator', 'representative'] as Role[]).map((r) => (
                <label key={r} className="grid gap-1 text-xs text-slate-600">{r === 'operator' ? '검수 담당 권한' : '최종 확인 권한'}
                  <input value={policy.roles[r]} maxLength={80} onChange={(e) => set({ roles: { ...policy.roles, [r]: e.target.value } })}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800" />
                </label>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-2 text-sm font-semibold text-slate-800">결재 단계</div>
            <div className="grid gap-2 text-sm">
              <label className="flex items-center gap-2"><input type="radio" name="steps" checked={!twoStep} onChange={() => setTwoStep(false)} className="accent-indigo-600" /> 1단계 · {policy.roles.representative} 최종 확인</label>
              <label className="flex items-center gap-2"><input type="radio" name="steps" checked={twoStep} onChange={() => setTwoStep(true)} className="accent-indigo-600" /> 2단계 · {policy.roles.operator} 검토 → {policy.roles.representative} 최종 결재</label>
              {twoStep && <p className="text-xs text-slate-500">2단계에서는 1단계와 2단계를 같은 사람이 처리할 수 없습니다.</p>}
            </div>
          </div>
        </div>
      </fieldset>

      {canEdit && (
        <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
          {!confirming ? (
            <button disabled={!dirty || busy || !policy.required_document_types.length} onClick={() => setConfirming(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">
              <Save size={16} /> 설정 저장
            </button>
          ) : (
            <div className="flex flex-wrap items-center gap-2 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
              저장하면 모든 계약을 다시 검사하고, 이미 결재한 계약도 다시 확인해야 합니다.
              <button onClick={() => void save()} disabled={busy} className="rounded-lg bg-amber-600 px-3 py-1.5 font-semibold text-white disabled:opacity-50">{busy ? '저장 중…' : '그래도 저장'}</button>
              <button onClick={() => setConfirming(false)} className="text-amber-800 underline">취소</button>
            </div>
          )}
          {dirty && !confirming && <button onClick={() => { setPolicy(saved); setConfirming(false); }} className="text-sm text-slate-500 underline">바꾼 내용 되돌리기</button>}
          {!policy.required_document_types.length && <span className="text-xs text-rose-600">필수 서류를 하나 이상 고르세요.</span>}
        </div>
      )}
      {notice && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    </section>
  );
};
