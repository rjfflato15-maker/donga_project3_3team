import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { PilotMetrics } from '../../types';

export const minutes = (s: number | null) => {
  if (s == null) return '기록 없음';
  if (s < 60) return '1분 미만';
  const total = Math.round(s / 60);
  const d = Math.floor(total / 1440), h = Math.floor((total % 1440) / 60), m = total % 60;
  return [d && `${d}일`, h && `${h}시간`, (m || (!d && !h)) && `${m}분`].filter(Boolean).join(' ');
};

/** 대시보드 아래 '업무 현황': 이 업무함에서 실제로 기록된 처리 시간과 보정 횟수 */
export const WorkStatsStrip: React.FC<{ refreshKey: unknown }> = ({ refreshKey }) => {
  const [m, setM] = useState<PilotMetrics | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api.pilotMetrics().then((v) => { if (active) { setM(v); setError(''); } }).catch((e) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [refreshKey]);
  if (error) return <p className="text-xs text-slate-500">업무 현황을 불러오지 못했습니다: {error}</p>;
  if (!m) return null;
  const items = [
    { label: '등록한 계약', value: `${m.contract_count}건` },
    { label: '결재 완료', value: `${m.confirmed_count}건` },
    { label: '서류 등록 → 첫 결재 평균', value: minutes(m.mean_elapsed_seconds), note: m.timed_contract_count ? `${m.timed_contract_count}건 기준` : '' },
    { label: '사람이 값을 고친 횟수', value: `${m.field_correction_count}회`, note: `서류 ${m.document_registration_count}건 중` },
  ];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4" aria-labelledby="stats-title">
      <div className="mb-3 flex flex-wrap items-baseline gap-2">
        <h2 id="stats-title" className="font-bold text-slate-900">업무 현황</h2>
        <span className="text-xs text-slate-500">이 업무함에 실제로 남은 기록 기준 · 대기 시간 포함</span>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {items.map((it) => (
          <div key={it.label} className="rounded-xl bg-slate-50 p-3">
            <div className="text-xs text-slate-500">{it.label}</div>
            <div className="text-lg font-bold tabular-nums text-slate-900">{it.value}</div>
            {it.note && <div className="text-[11px] text-slate-400">{it.note}</div>}
          </div>
        ))}
      </div>
    </section>
  );
};
