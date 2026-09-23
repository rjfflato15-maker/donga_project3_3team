import React from 'react';
import { ContractListItem } from '../types';
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  FileCheck2,
  PieChart,
  TrendingUp,
  Edit3,
  Trash2,
} from 'lucide-react';

interface OverallDashboardViewProps {
  contracts: ContractListItem[];
  onSelectContract: (contractId: number) => void;
  onViewAllContracts: () => void;
  onEditContract?: (contract: ContractListItem) => void;
  onDeleteContract?: (contractId: number, title: string) => void;
  onOpenAutoBatchContract?: () => void;
}

export const OverallDashboardView: React.FC<OverallDashboardViewProps> = ({
  contracts,
  onSelectContract,
  onViewAllContracts,
  onEditContract,
  onDeleteContract,
  onOpenAutoBatchContract,
}) => {
  const totalCount = contracts.length;

  let passCount = 0;
  let reviewCount = 0;
  let failMissingCount = 0;

  contracts.forEach((c) => {
    const status = c.review_status?.toUpperCase();
    if (status === 'PASS') {
      passCount += 1;
    } else if (status === 'REVIEW') {
      reviewCount += 1;
    } else {
      failMissingCount += 1;
    }
  });

  const getContractCode = (index: number, id: number) => {
    const letters = ['A101', 'B202', 'C303', 'D404', 'E505', 'F606'];
    const suffix = letters[index % letters.length] || `${100 + id}`;
    return `CT-2026-${suffix}`;
  };

  const getStatusBadge = (reviewStatus: string, completenessRate: number) => {
    const status = reviewStatus?.toUpperCase();
    if (status === 'PASS') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-black bg-emerald-50 text-emerald-700 border border-emerald-200/80 shadow-2xs">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          <span>검수 통과 (PASS)</span>
        </span>
      );
    }
    if (completenessRate < 100) {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-black bg-purple-50 text-purple-700 border border-purple-200/80 shadow-2xs">
          <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span>
          <span>증빙 누락 (MISSING)</span>
        </span>
      );
    }
    if (status === 'REVIEW') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-black bg-amber-50 text-amber-700 border border-amber-200/80 shadow-2xs">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
          <span>재확인 필요 (REVIEW)</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-black bg-rose-50 text-rose-700 border border-rose-200/80 shadow-2xs">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
        <span>검수 부적격 (FAIL)</span>
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Sleek Hero Banner Section */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-xl shadow-slate-900/10 relative overflow-hidden">
        {/* Background Decorative Pattern */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-indigo-500/10 to-transparent pointer-events-none"></div>
        <div className="absolute -right-10 -bottom-10 w-48 h-48 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none"></div>

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center space-x-2 bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 px-3 py-1 rounded-full text-xs font-bold backdrop-blur-xs">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              <span>실시간 AI 서류 분류 &amp; 룰 엔진 교차검수</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white">
              계약 증빙 검수 대시보드
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 max-w-xl font-medium leading-relaxed">
              외주·용역 계약 건별 6종 필수 서류의 자동 수집, AI PII 마스킹, 국세청 진위확인 및 룰 엔진 불일치 대조 결과를 모니터링합니다.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            {onOpenAutoBatchContract && (
              <button
                onClick={onOpenAutoBatchContract}
                className="px-4 py-3 bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-500 hover:to-amber-600 text-slate-950 font-black text-xs rounded-2xl shadow-lg shadow-amber-500/20 transition-all hover:scale-[1.02] flex items-center justify-center space-x-2 border border-amber-300"
              >
                <span className="text-base">⚡</span>
                <span>6종 서류로 계약 자동 생성</span>
              </button>
            )}

            <div className="flex items-center space-x-3 bg-white/10 backdrop-blur-md border border-white/15 p-4 rounded-2xl shrink-0">
              <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white flex items-center justify-center font-black text-lg shadow-md shadow-indigo-600/30">
                {totalCount > 0 ? `${Math.round((passCount / totalCount) * 100)}%` : '0%'}
              </div>
              <div>
                <div className="text-xs font-bold text-slate-300">전체 검수 통과율</div>
                <div className="text-sm font-black text-white flex items-center space-x-1 mt-0.5">
                  <span>{passCount} / {totalCount} 건 통과</span>
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-400 inline ml-1" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Top 4 KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Total Contracts */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-xs hover:shadow-lg hover:-translate-y-1 transition-all duration-300 relative overflow-hidden group">
          <div className="absolute top-0 left-0 right-0 h-1 bg-indigo-600"></div>
          <div className="flex items-center justify-between text-xs font-bold text-slate-500">
            <span>총 등록 계약 건수</span>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center group-hover:scale-110 transition-transform">
              <FileCheck2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-black text-slate-900 tracking-tight mt-3">
            {totalCount} <span className="text-sm font-bold text-slate-500">건</span>
          </div>
          <div className="mt-3 text-[11px] font-semibold text-slate-400 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
            <span>시스템 등록 완료</span>
          </div>
        </div>

        {/* Card 2: PASS */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-xs hover:shadow-lg hover:-translate-y-1 transition-all duration-300 relative overflow-hidden group">
          <div className="absolute top-0 left-0 right-0 h-1 bg-emerald-500"></div>
          <div className="flex items-center justify-between text-xs font-bold text-emerald-600">
            <span>검수 완료 (PASS)</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-110 transition-transform">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-black text-emerald-600 tracking-tight mt-3">
            {passCount} <span className="text-sm font-bold text-emerald-700">건</span>
          </div>
          <div className="mt-3 text-[11px] font-semibold text-emerald-600/80 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>모든 규칙 이상 없음</span>
          </div>
        </div>

        {/* Card 3: REVIEW */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-xs hover:shadow-lg hover:-translate-y-1 transition-all duration-300 relative overflow-hidden group">
          <div className="absolute top-0 left-0 right-0 h-1 bg-amber-500"></div>
          <div className="flex items-center justify-between text-xs font-bold text-amber-600">
            <span>재확인 필요 (REVIEW)</span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center group-hover:scale-110 transition-transform">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-black text-amber-600 tracking-tight mt-3">
            {reviewCount} <span className="text-sm font-bold text-amber-700">건</span>
          </div>
          <div className="mt-3 text-[11px] font-semibold text-amber-600/80 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
            <span>담당자 정밀 확인 권장</span>
          </div>
        </div>

        {/* Card 4: FAIL / MISSING */}
        <div className="bg-white rounded-2xl p-5 border border-slate-200/80 shadow-xs hover:shadow-lg hover:-translate-y-1 transition-all duration-300 relative overflow-hidden group">
          <div className="absolute top-0 left-0 right-0 h-1 bg-rose-500"></div>
          <div className="flex items-center justify-between text-xs font-bold text-rose-600">
            <span>부적격/불일치 (FAIL / MISSING)</span>
            <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center group-hover:scale-110 transition-transform">
              <AlertCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-black text-rose-600 tracking-tight mt-3">
            {failMissingCount} <span className="text-sm font-bold text-rose-700">건</span>
          </div>
          <div className="mt-3 text-[11px] font-semibold text-rose-600/80 flex items-center space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
            <span>서류 누락 또는 금액 차액</span>
          </div>
        </div>
      </div>

      {/* Main Table: Recent Contracts Inspection Status */}
      <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        {/* Table Header Controls */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
              <PieChart className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-extrabold text-slate-900">
                최근 등록 계약 검수 현황
              </h2>
              <p className="text-[11px] text-slate-400 font-semibold">
                클릭 시 상세 6종 서류 체크리스트 및 대조 리포트로 이동합니다.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {onOpenAutoBatchContract && (
              <button
                onClick={onOpenAutoBatchContract}
                className="flex items-center space-x-1.5 text-xs font-extrabold text-amber-900 bg-amber-300 hover:bg-amber-400 px-3 py-1.5 rounded-xl transition-all border border-amber-400 shadow-2xs"
              >
                <span>⚡ 6종 서류로 계약 생성</span>
              </button>
            )}

            <button
              onClick={onViewAllContracts}
              className="flex items-center space-x-1.5 text-xs font-extrabold text-indigo-700 hover:text-indigo-900 bg-indigo-50 hover:bg-indigo-100/80 px-3.5 py-1.5 rounded-xl transition-all duration-200 border border-indigo-100 shadow-2xs"
            >
              <span>전체 목록 보기</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Table View */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50/90 border-b border-slate-200/60 text-slate-500 font-extrabold uppercase tracking-wider text-[11px]">
                <th className="py-3.5 px-5">계약 코드</th>
                <th className="py-3.5 px-5">계약 명칭</th>
                <th className="py-3.5 px-5">상대 업체명</th>
                <th className="py-3.5 px-5">계약 금액</th>
                <th className="py-3.5 px-5">검수 상태</th>
                <th className="py-3.5 px-5 text-center">동작</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {contracts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400 font-semibold">
                    등록된 계약이 없습니다. 상단 '새 계약 등록' 버튼을 눌러 추가하세요.
                  </td>
                </tr>
              ) : (
                contracts.map((c, idx) => (
                  <tr
                    key={c.contract_id}
                    className="hover:bg-indigo-50/40 transition-colors group cursor-pointer"
                    onClick={() => onSelectContract(c.contract_id)}
                  >
                    <td className="py-4 px-5 font-bold text-indigo-600 group-hover:underline">
                      {getContractCode(idx, c.contract_id)}
                    </td>
                    <td className="py-4 px-5 font-extrabold text-slate-900 max-w-xs truncate">
                      {c.title}
                    </td>
                    <td className="py-4 px-5 font-semibold text-slate-600">
                      {c.vendor_name}
                    </td>
                    <td className="py-4 px-5 font-black text-slate-900">
                      ₩{c.contract_amount.toLocaleString()}
                    </td>
                    <td className="py-4 px-5">
                      {getStatusBadge(c.review_status, c.completeness_rate)}
                    </td>
                    <td className="py-4 px-5 text-center">
                      <div className="flex items-center justify-center space-x-2">
                        {onEditContract && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onEditContract(c);
                            }}
                            className="inline-flex items-center space-x-1 px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 border border-slate-200 hover:border-indigo-300 rounded-xl font-bold text-slate-700 shadow-2xs transition-all duration-200 text-[11px]"
                            title="계약 정보 수정"
                          >
                            <Edit3 className="w-3 h-3 text-slate-500" />
                            <span>수정</span>
                          </button>
                        )}
                        {onDeleteContract && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteContract(c.contract_id, c.title);
                            }}
                            className="inline-flex items-center space-x-1 px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl font-bold shadow-2xs transition-all duration-200 text-[11px]"
                            title="계약 정보 삭제"
                          >
                            <Trash2 className="w-3 h-3 text-rose-600" />
                            <span>삭제</span>
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectContract(c.contract_id);
                          }}
                          className="px-3.5 py-1.5 bg-white hover:bg-indigo-600 hover:text-white border border-slate-200 hover:border-indigo-600 rounded-xl font-bold text-slate-700 shadow-2xs transition-all duration-200 text-[11px]"
                        >
                          리포트 확인
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
