import React from 'react';
import { ContractDetail } from '../types';
import { CheckCircle2, Layers } from 'lucide-react';

interface MetricsSummaryProps {
  contract: ContractDetail;
}

export const MetricsSummary: React.FC<MetricsSummaryProps> = ({ contract }) => {
  const { summary } = contract;
  const reviewNeededCount = summary.fail_count + summary.missing_count + summary.review_count;

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm mb-6">
      {/* Top row: Title and Alert Badge */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-100">
        <div>
          <div className="flex items-center space-x-2 text-xs font-bold text-blue-600 uppercase tracking-wider mb-1">
            <span>외주·용역 계약 증빙 검수</span>
            <span>•</span>
            <span>ID #{contract.contract_id}</span>
          </div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
            {contract.title}
          </h1>
          <div className="flex items-center space-x-4 mt-1.5 text-xs text-slate-500">
            <span>거래처: <strong className="text-slate-700">{contract.vendor_name}</strong></span>
            <span>사업자번호: <strong className="text-slate-700">{contract.business_number}</strong></span>
            <span>총 계약금액: <strong className="text-blue-700">{contract.contract_amount.toLocaleString()}원</strong></span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {reviewNeededCount > 0 ? (
            <div className="flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800 text-xs font-bold shadow-sm">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
              <span>EXCEPTION REVIEW</span>
              <span className="bg-amber-200/60 px-1.5 py-0.5 rounded text-[11px]">검토 필요 {reviewNeededCount}건</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>ALL PASSED · 정상 검수 완료</span>
            </div>
          )}
        </div>
      </div>

      {/* Middle row: Completeness Rate Gauge */}
      <div className="mt-5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-bold text-slate-800">증빙 충족률</span>
            <span className="text-xs text-slate-500">
              ({summary.submitted_document_count} / {summary.required_document_count}종 필수 서류 제출)
            </span>
          </div>
          <div className="text-2xl font-black text-blue-600 tracking-tight">
            {summary.completeness_rate}%
          </div>
        </div>

        {/* Progress Bar matching slide design */}
        <div className="w-full h-3.5 bg-slate-100 rounded-full overflow-hidden p-0.5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 transition-all duration-700 shadow-sm"
            style={{ width: `${Math.min(100, Math.max(0, summary.completeness_rate))}%` }}
          />
        </div>
      </div>

      {/* Bottom KPI stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5 pt-4 border-t border-slate-100">
        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-100">
          <span className="text-[11px] font-semibold text-slate-500 block">정상 통과 (PASS)</span>
          <span className="text-lg font-black text-emerald-600">{summary.pass_count}건</span>
        </div>

        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-100">
          <span className="text-[11px] font-semibold text-slate-500 block">불일치 항목 (FAIL)</span>
          <span className="text-lg font-black text-rose-600">{summary.fail_count}건</span>
        </div>

        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-100">
          <span className="text-[11px] font-semibold text-slate-500 block">필수 서류 누락</span>
          <span className="text-lg font-black text-amber-600">{summary.missing_count}건</span>
        </div>

        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-100">
          <span className="text-[11px] font-semibold text-slate-500 block">정보 일치율 / 불일치율</span>
          <span className="text-sm font-bold text-slate-800">
            {summary.match_rate !== null ? `${summary.match_rate}%` : '-'} /{' '}
            <span className="text-rose-600">{summary.mismatch_rate !== null ? `${summary.mismatch_rate}%` : '-'}</span>
          </span>
        </div>
      </div>
    </div>
  );
};
