import React from 'react';
import { ContractDetail } from '../types';
import { RuleValidationCard } from './RuleValidationCard';
import { Activity, RefreshCw } from 'lucide-react';

interface ValidationReportViewProps {
  currentContract: ContractDetail | null;
  onOpenSimulator: () => void;
  onRevalidate: () => void;
  loading: boolean;
}

export const ValidationReportView: React.FC<ValidationReportViewProps> = ({
  currentContract,
  onOpenSimulator,
  onRevalidate,
  loading,
}) => {
  if (!currentContract) {
    return (
      <div className="bg-white rounded-2xl p-12 border border-slate-200 text-center text-slate-400 font-semibold">
        선택된 계약 정보가 없습니다.
      </div>
    );
  }

  const { summary } = currentContract;

  return (
    <div className="space-y-6">
      {/* Header Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            AI 교차검수 리포트
          </h1>
          <p className="text-xs text-slate-500 font-medium mt-1">
            계약명: <strong className="text-slate-800">{currentContract.title}</strong> (ID #{currentContract.contract_id})
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onRevalidate}
            disabled={loading}
            className="flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>룰 엔진 재검수</span>
          </button>

          <button
            onClick={onOpenSimulator}
            className="flex items-center space-x-1.5 px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-sm rounded-xl transition-colors"
          >
            <Activity className="w-4 h-4" />
            <span>5단계 파이프라인 시뮬레이션</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-500">필수 증빙 충족률</span>
          <div className="text-2xl font-black text-indigo-600 mt-1">
            {summary.completeness_rate}%
          </div>
        </div>

        <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-500">정상 통과 (PASS)</span>
          <div className="text-2xl font-black text-emerald-600 mt-1">
            {summary.pass_count} 건
          </div>
        </div>

        <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-500">불일치 (FAIL)</span>
          <div className="text-2xl font-black text-rose-600 mt-1">
            {summary.fail_count} 건
          </div>
        </div>

        <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-xs">
          <span className="text-xs font-bold text-slate-500">필수 서류 누락 (MISSING)</span>
          <div className="text-2xl font-black text-amber-600 mt-1">
            {summary.missing_count} 건
          </div>
        </div>
      </div>

      {/* Detailed Rule Engine Breakdown */}
      <RuleValidationCard checks={currentContract.checks} />
    </div>
  );
};
