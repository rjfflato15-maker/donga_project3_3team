import React from 'react';
import { ContractDetail } from '../types';
import {
  CheckCircle2,
  Layers,
  Edit3,
  Building2,
  FileSpreadsheet,
  CreditCard,
  Clock,
  Trash2,
} from 'lucide-react';

interface MetricsSummaryProps {
  contract: ContractDetail;
  onEditContract?: () => void;
  onDeleteContract?: () => void;
}

export const MetricsSummary: React.FC<MetricsSummaryProps> = ({
  contract,
  onEditContract,
  onDeleteContract,
}) => {
  const { summary } = contract;
  const reviewNeededCount = summary.fail_count + summary.missing_count + summary.review_count;

  const formatDate = (isoString?: string) => {
    if (!isoString) return '-';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm mb-6 space-y-6">
      {/* Top Header Card: Detailed Contract Information Display */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-5 text-white shadow-md relative overflow-hidden">
        {/* Background accent */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-indigo-500/10 to-transparent pointer-events-none"></div>

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center space-x-2 text-xs font-bold text-indigo-300">
              <span className="bg-indigo-500/20 border border-indigo-400/30 px-2.5 py-0.5 rounded-full">
                외주·용역 계약 상세 정보
              </span>
              <span>•</span>
              <span className="font-mono text-indigo-200">ID #{contract.contract_id}</span>
            </div>

            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center space-x-2">
              <span>{contract.title}</span>
            </h1>

            {/* Contract Core Info Badges Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 text-xs">
              <div className="flex items-center space-x-2 bg-white/10 backdrop-blur-xs px-3 py-2 rounded-xl border border-white/10">
                <Building2 className="w-4 h-4 text-indigo-300 shrink-0" />
                <div className="truncate">
                  <span className="text-slate-400 block text-[10px] font-semibold">거래처명</span>
                  <strong className="text-white font-bold">{contract.vendor_name}</strong>
                </div>
              </div>

              <div className="flex items-center space-x-2 bg-white/10 backdrop-blur-xs px-3 py-2 rounded-xl border border-white/10">
                <CreditCard className="w-4 h-4 text-indigo-300 shrink-0" />
                <div className="truncate">
                  <span className="text-slate-400 block text-[10px] font-semibold">사업자등록번호</span>
                  <strong className="text-white font-mono font-bold">{contract.business_number}</strong>
                </div>
              </div>

              <div className="flex items-center space-x-2 bg-white/10 backdrop-blur-xs px-3 py-2 rounded-xl border border-white/10">
                <FileSpreadsheet className="w-4 h-4 text-emerald-400 shrink-0" />
                <div className="truncate">
                  <span className="text-slate-400 block text-[10px] font-semibold">총 계약금액</span>
                  <strong className="text-emerald-300 font-extrabold text-sm">
                    ₩{contract.contract_amount.toLocaleString()}
                  </strong>
                </div>
              </div>

              <div className="flex items-center space-x-2 bg-white/10 backdrop-blur-xs px-3 py-2 rounded-xl border border-white/10">
                <Clock className="w-4 h-4 text-indigo-300 shrink-0" />
                <div className="truncate">
                  <span className="text-slate-400 block text-[10px] font-semibold">최근 수정일시</span>
                  <strong className="text-slate-200 text-[11px] font-medium">
                    {formatDate(contract.updated_at)}
                  </strong>
                </div>
              </div>
            </div>
          </div>

          {/* Action & Status Box */}
          <div className="flex flex-col sm:flex-row md:flex-col items-start sm:items-center md:items-end justify-between gap-3 border-t md:border-t-0 md:border-l border-white/10 pt-3 md:pt-0 md:pl-5">
            {reviewNeededCount > 0 ? (
              <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-amber-500/20 border border-amber-400/40 text-amber-200 text-xs font-bold">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
                <span>검토 필요 {reviewNeededCount}건</span>
              </div>
            ) : (
              <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-400/40 text-emerald-200 text-xs font-bold">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>ALL PASSED · 정상</span>
              </div>
            )}

            <div className="flex items-center space-x-2">
              {onEditContract && (
                <button
                  onClick={onEditContract}
                  className="inline-flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white px-3.5 py-1.5 rounded-xl text-xs font-extrabold shadow-md transition-all hover:scale-[1.02] active:scale-[0.98]"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  <span>수정</span>
                </button>
              )}
              {onDeleteContract && (
                <button
                  onClick={onDeleteContract}
                  className="inline-flex items-center space-x-1.5 bg-rose-600/80 hover:bg-rose-600 text-white px-3.5 py-1.5 rounded-xl text-xs font-extrabold shadow-md transition-all hover:scale-[1.02] active:scale-[0.98]"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>삭제</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Middle row: Completeness Rate Gauge */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <Layers className="w-4 h-4 text-indigo-600" />
            <span className="text-sm font-bold text-slate-800">증빙 충족률</span>
            <span className="text-xs text-slate-500 font-semibold">
              ({summary.submitted_document_count} / {summary.required_document_count}종 필수 서류 제출)
            </span>
          </div>
          <div className="text-2xl font-black text-indigo-600 tracking-tight">
            {summary.completeness_rate}%
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-3.5 bg-slate-100 rounded-full overflow-hidden p-0.5 border border-slate-200/60">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-indigo-700 transition-all duration-700 shadow-xs"
            style={{ width: `${Math.min(100, Math.max(0, summary.completeness_rate))}%` }}
          />
        </div>
      </div>

      {/* Bottom KPI stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-200/60">
          <span className="text-[11px] font-semibold text-slate-500 block">정상 통과 (PASS)</span>
          <span className="text-lg font-black text-emerald-600">{summary.pass_count}건</span>
        </div>

        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-200/60">
          <span className="text-[11px] font-semibold text-slate-500 block">불일치 항목 (FAIL)</span>
          <span className="text-lg font-black text-rose-600">{summary.fail_count}건</span>
        </div>

        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-200/60">
          <span className="text-[11px] font-semibold text-slate-500 block">필수 서류 누락</span>
          <span className="text-lg font-black text-amber-600">{summary.missing_count}건</span>
        </div>

        <div className="bg-slate-50/80 rounded-xl p-3 border border-slate-200/60">
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
