import React, { useState, useMemo } from 'react';
import {
  ContractListItem,
  DocumentType,
} from '../types';
import {
  FileText,
  Search,
  Sparkles,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Trash2,
  Edit3,
  ExternalLink,
  RefreshCw,
  ShieldCheck,
  Calendar,
} from 'lucide-react';
import { maskBusinessNumber, maskVendorName } from '../utils/masking';

interface ContractsListViewProps {
  contracts: ContractListItem[];
  currentContractId?: number | null;
  onSelectContract: (contractId: number) => void;
  onOpenAutoBatchContract?: () => void;
  onEditContract: (contract: ContractListItem) => void;
  onDeleteContract: (contractId: number, title?: string) => void;
  onSeedDemo?: () => void;
  actionLoading?: boolean;
  isMaskingEnabled?: boolean;
}

const CORE_DOCS: { type: DocumentType; label: string; short: string }[] = [
  { type: 'contract', label: '외주계약서', short: '계약' },
  { type: 'estimate', label: '견적서', short: '견적' },
  { type: 'business_registration', label: '사업자등록증', short: '등록증' },
  { type: 'bank_account', label: '통장사본', short: '통장' },
  { type: 'tax_invoice', label: '세금계산서', short: '세금' },
  { type: 'inspection_confirmation', label: '검수확인서', short: '검수' },
];

export const ContractsListView: React.FC<ContractsListViewProps> = ({
  contracts,
  currentContractId,
  onSelectContract,
  onOpenAutoBatchContract,
  onEditContract,
  onDeleteContract,
  onSeedDemo,
  actionLoading = false,
  isMaskingEnabled = true,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'PASS' | 'FLAGGED' | 'INCOMPLETE' | 'PENDING'>('ALL');
  const [sortBy, setSortBy] = useState<'latest' | 'amount_desc' | 'amount_asc' | 'completeness_desc' | 'title'>('latest');

  // Stats
  const totalCount = contracts.length;
  const passCount = contracts.filter((c) => c.review_status === 'PASS').length;
  const flaggedCount = contracts.filter((c) => c.review_status === 'FLAGGED').length;
  const incompleteCount = contracts.filter((c) => c.review_status === 'INCOMPLETE' || c.completeness_rate < 100).length;
  const totalAmount = contracts.reduce((acc, c) => acc + (c.contract_amount || 0), 0);

  // Filtered & Sorted Contracts
  const filteredContracts = useMemo(() => {
    return contracts
      .filter((c) => {
        // Status filter
        if (statusFilter === 'PASS' && c.review_status !== 'PASS') return false;
        if (statusFilter === 'FLAGGED' && c.review_status !== 'FLAGGED') return false;
        if (statusFilter === 'INCOMPLETE' && c.review_status !== 'INCOMPLETE' && c.completeness_rate >= 100) return false;
        if (statusFilter === 'PENDING' && c.review_status !== 'PENDING') return false;

        // Search term
        if (searchTerm.trim()) {
          const q = searchTerm.toLowerCase();
          const titleMatch = c.title.toLowerCase().includes(q);
          const vendorMatch = c.vendor_name.toLowerCase().includes(q);
          const bizMatch = c.business_number.toLowerCase().includes(q);
          const idMatch = String(c.contract_id).includes(q) || `ct-${c.contract_id}`.includes(q);
          return titleMatch || vendorMatch || bizMatch || idMatch;
        }

        return true;
      })
      .sort((a, b) => {
        switch (sortBy) {
          case 'amount_desc':
            return b.contract_amount - a.contract_amount;
          case 'amount_asc':
            return a.contract_amount - b.contract_amount;
          case 'completeness_desc':
            return b.completeness_rate - a.completeness_rate;
          case 'title':
            return a.title.localeCompare(b.title, 'ko');
          case 'latest':
          default:
            return b.contract_id - a.contract_id;
        }
      });
  }, [contracts, statusFilter, searchTerm, sortBy]);

  const getContractCode = (id: number) => {
    const year = 2026;
    const padded = String(id).padStart(3, '0');
    return `CT-${year}-${padded}`;
  };

  const getStatusBadge = (status: string, completeness: number) => {
    if (status === 'PASS' && completeness >= 100) {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-black bg-emerald-100 text-emerald-800 border border-emerald-300">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
          <span>검수 통과 (PASS)</span>
        </span>
      );
    }
    if (status === 'FLAGGED') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-black bg-amber-100 text-amber-900 border border-amber-300">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
          <span>불일치 주의 (FLAGGED)</span>
        </span>
      );
    }
    if (completeness < 100 || status === 'INCOMPLETE') {
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-black bg-indigo-100 text-indigo-900 border border-indigo-300">
          <Clock className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
          <span>서류 미흡 ({completeness}%)</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-[11px] font-black bg-slate-100 text-slate-700 border border-slate-300">
        <Clock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
        <span>대기 중</span>
      </span>
    );
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return '-';
    try {
      const d = new Date(isoString);
      return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-xl shadow-slate-900/10 relative overflow-hidden">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute bottom-0 left-1/3 -mb-10 w-60 h-60 bg-blue-500/10 rounded-full blur-2xl pointer-events-none"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center space-x-2 bg-indigo-500/20 border border-indigo-400/30 text-indigo-300 px-3 py-1 rounded-full text-xs font-bold backdrop-blur-xs">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              <span>외주·용역 계약 전주기 관리 &amp; 6종 증빙 자동검수</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white flex items-center space-x-3">
              <span>외주/용역 계약 관리</span>
              <span className="text-xs font-black bg-white/15 text-indigo-200 px-2.5 py-1 rounded-lg">
                총 {totalCount}건
              </span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 max-w-2xl font-medium leading-relaxed">
              등록된 모든 외주 및 용역 계약을 목록 형태로 조회하고, 6종 필수 증빙서류 구비율과 AI 교차검수 결과를 한눈에 확인·관리합니다.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3">
            {onOpenAutoBatchContract && (
              <button
                onClick={onOpenAutoBatchContract}
                className="px-3.5 py-2.5 bg-white/10 hover:bg-white/15 text-slate-200 font-bold text-xs rounded-xl border border-white/20 transition-colors flex items-center space-x-1.5 hover:scale-[1.02] active:scale-95 whitespace-nowrap shrink-0"
                title="6종 서류를 업로드하여 계약 내용, 금액, 사업자번호, 날짜 자동 생성"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                <span>6종 서류로 계약 자동 생성</span>
              </button>
            )}

            {onSeedDemo && (
              <button
                onClick={onSeedDemo}
                disabled={actionLoading}
                className="px-3.5 py-2.5 bg-white/10 hover:bg-white/15 text-slate-200 font-bold text-xs rounded-xl border border-white/20 transition-colors flex items-center space-x-1.5 whitespace-nowrap shrink-0"
                title="기획서 데모 시나리오 불러오기"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin text-indigo-400' : ''}`} />
                <span>데모 초기화</span>
              </button>
            )}
          </div>
        </div>

        {/* 4 Summary Mini Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-6 border-t border-white/10">
          <div className="bg-white/5 backdrop-blur-sm rounded-xl p-3 border border-white/10">
            <div className="text-[11px] font-bold text-slate-400">총 계약 체결액</div>
            <div className="text-base sm:text-lg font-black text-white mt-0.5 truncate">
              ₩{totalAmount.toLocaleString()}
            </div>
          </div>

          <div className="bg-white/5 backdrop-blur-sm rounded-xl p-3 border border-white/10">
            <div className="text-[11px] font-bold text-emerald-400">검수 통과 (PASS)</div>
            <div className="text-base sm:text-lg font-black text-emerald-300 mt-0.5">
              {passCount} <span className="text-xs font-semibold text-slate-400">건 ({totalCount > 0 ? Math.round((passCount / totalCount) * 100) : 0}%)</span>
            </div>
          </div>

          <div className="bg-white/5 backdrop-blur-sm rounded-xl p-3 border border-white/10">
            <div className="text-[11px] font-bold text-amber-400">불일치 주의 (FLAGGED)</div>
            <div className="text-base sm:text-lg font-black text-amber-300 mt-0.5">
              {flaggedCount} <span className="text-xs font-semibold text-slate-400">건</span>
            </div>
          </div>

          <div className="bg-white/5 backdrop-blur-sm rounded-xl p-3 border border-white/10">
            <div className="text-[11px] font-bold text-indigo-300">서류 미흡 (INCOMPLETE)</div>
            <div className="text-base sm:text-lg font-black text-indigo-200 mt-0.5">
              {incompleteCount} <span className="text-xs font-semibold text-slate-400">건</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filter, Search & Controls Bar */}
      <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-xs flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
        {/* Status Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 p-1 bg-slate-100 rounded-xl text-xs font-bold">
          <button
            onClick={() => setStatusFilter('ALL')}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              statusFilter === 'ALL'
                ? 'bg-white text-slate-900 shadow-xs font-extrabold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            전체 ({totalCount})
          </button>
          <button
            onClick={() => setStatusFilter('PASS')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center space-x-1 ${
              statusFilter === 'PASS'
                ? 'bg-emerald-600 text-white shadow-xs font-extrabold'
                : 'text-emerald-700 hover:bg-emerald-50'
            }`}
          >
            <span>통과</span>
            <span className="text-[10px] px-1 py-0.2 rounded-full bg-emerald-100 text-emerald-800 font-black">
              {passCount}
            </span>
          </button>
          <button
            onClick={() => setStatusFilter('FLAGGED')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center space-x-1 ${
              statusFilter === 'FLAGGED'
                ? 'bg-amber-500 text-slate-950 shadow-xs font-extrabold'
                : 'text-amber-800 hover:bg-amber-50'
            }`}
          >
            <span>주의/불일치</span>
            <span className="text-[10px] px-1 py-0.2 rounded-full bg-amber-100 text-amber-900 font-black">
              {flaggedCount}
            </span>
          </button>
          <button
            onClick={() => setStatusFilter('INCOMPLETE')}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center space-x-1 ${
              statusFilter === 'INCOMPLETE'
                ? 'bg-indigo-600 text-white shadow-xs font-extrabold'
                : 'text-indigo-700 hover:bg-indigo-50'
            }`}
          >
            <span>서류 미흡</span>
            <span className="text-[10px] px-1 py-0.2 rounded-full bg-indigo-100 text-indigo-900 font-black">
              {incompleteCount}
            </span>
          </button>
        </div>

        {/* Search & Sort */}
        <div className="flex items-center space-x-2.5">
          {/* Search Box */}
          <div className="relative flex-1 sm:w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="계약명, 업체명, 사업자번호 검색..."
              className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all placeholder:text-slate-400"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            )}
          </div>

          {/* Sort Selector */}
          <div className="relative shrink-0">
            <select
              value={sortBy}
              onChange={(e: any) => setSortBy(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 cursor-pointer"
            >
              <option value="latest">최신 등록순</option>
              <option value="amount_desc">금액 높은순</option>
              <option value="amount_asc">금액 낮은순</option>
              <option value="completeness_desc">서류 충족률순</option>
              <option value="title">계약명 가나다순</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Contracts Table */}
      <div className="bg-white rounded-3xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-[1050px] w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50/90 border-b border-slate-200/80 text-slate-500 font-extrabold uppercase tracking-wider text-[11px]">
                <th className="py-4 px-5 w-24">계약 코드</th>
                <th className="py-4 px-5">외주/용역 계약 정보</th>
                <th className="py-4 px-5">협력 업체</th>
                <th className="py-4 px-5">계약 금액</th>
                <th className="py-4 px-5">6종 필수 서류 현황</th>
                <th className="py-4 px-5">AI 검수 판정</th>
                <th className="py-4 px-5 w-28">등록일</th>
                <th className="py-4 px-5 text-center w-36">관리 동작</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredContracts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-slate-400">
                    <div className="flex flex-col items-center justify-center space-y-3">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400">
                        <FileText className="w-6 h-6" />
                      </div>
                      <p className="text-sm font-bold text-slate-700">
                        {searchTerm ? '검색 조건과 일치하는 계약이 없습니다.' : '등록된 외주/용역 계약이 없습니다.'}
                      </p>
                      <p className="text-xs text-slate-400">
                        {searchTerm ? '다른 검색어를 입력하시거나 필터를 초기화해 보세요.' : '6종 서류 자동 일괄 등록을 통해 계약을 추가하세요.'}
                      </p>
                      {searchTerm ? (
                        <button
                          onClick={() => {
                            setSearchTerm('');
                            setStatusFilter('ALL');
                          }}
                          className="mt-2 px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-bold transition-colors"
                        >
                          필터 초기화
                        </button>
                      ) : (
                        <div className="flex items-center space-x-2 mt-2">
                          {onOpenAutoBatchContract && (
                            <button
                              onClick={onOpenAutoBatchContract}
                              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 border border-slate-200/80 shadow-2xs"
                            >
                              <Sparkles className="w-3.5 h-3.5 text-amber-500 fill-amber-400" />
                              <span>6종 서류로 계약 자동 생성</span>
                            </button>
                          )}
                          {onSeedDemo && (
                            <button
                              onClick={onSeedDemo}
                              className="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl text-xs font-bold hover:bg-slate-200 transition-all"
                            >
                              데모 데이터 생성
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filteredContracts.map((c) => {
                  const isSelected = currentContractId === c.contract_id;
                  const submittedTypes = c.submitted_document_types || [];

                  return (
                    <tr
                      key={c.contract_id}
                      onClick={() => onSelectContract(c.contract_id)}
                      className={`hover:bg-indigo-50/40 transition-colors group cursor-pointer ${
                        isSelected ? 'bg-indigo-50/60 border-l-4 border-l-indigo-600' : ''
                      }`}
                    >
                      {/* Contract Code */}
                      <td className="py-4 px-5">
                        <span className="font-mono font-black text-indigo-600 bg-indigo-50 group-hover:bg-indigo-100 px-2 py-1 rounded-md text-[11px] transition-colors border border-indigo-200/60">
                          {getContractCode(c.contract_id)}
                        </span>
                      </td>

                      {/* Title & Info */}
                      <td className="py-4 px-5">
                        <div className="font-black text-slate-900 group-hover:text-indigo-600 text-sm transition-colors flex items-center space-x-1.5">
                          <span>{c.title}</span>
                          {isSelected && (
                            <span className="text-[10px] bg-indigo-600 text-white px-1.5 py-0.2 rounded font-bold">
                              선택됨
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400 font-medium mt-0.5 flex items-center space-x-2">
                          <span>
                            사업자등록번호: {c.business_number ? (isMaskingEnabled ? maskBusinessNumber(c.business_number) : c.business_number) : '미등록'}
                          </span>
                        </div>
                      </td>

                      {/* Vendor */}
                      <td className="py-4 px-5">
                        <div className="flex items-center space-x-1.5 font-bold text-slate-800">
                          <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <span>{maskVendorName(c.vendor_name, isMaskingEnabled)}</span>
                        </div>
                      </td>

                      {/* Amount */}
                      <td className="py-4 px-5">
                        <div className="font-black text-slate-900 text-sm">
                          ₩{c.contract_amount.toLocaleString()}
                        </div>
                      </td>

                      {/* 6 Core Docs Status */}
                      <td className="py-4 px-5">
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-extrabold text-slate-700">
                              {c.submitted_docs_count} / {c.total_docs_count || 6} 제출
                            </span>
                            <span className="font-black text-indigo-600">{c.completeness_rate}%</span>
                          </div>

                          {/* Progress Bar */}
                          <div className="w-32 bg-slate-100 h-1.5 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-300 ${
                                c.completeness_rate >= 100
                                  ? 'bg-emerald-500'
                                  : c.completeness_rate >= 50
                                  ? 'bg-indigo-500'
                                  : 'bg-amber-500'
                              }`}
                              style={{ width: `${Math.min(c.completeness_rate, 100)}%` }}
                            ></div>
                          </div>

                          {/* 6 Document Type Mini Badges */}
                          <div className="flex items-center space-x-1 pt-1">
                            {CORE_DOCS.map((doc) => {
                              const isSubmitted = submittedTypes.includes(doc.type);
                              return (
                                <span
                                  key={doc.type}
                                  title={`${doc.label}: ${isSubmitted ? '제출 완료' : '미제출'}`}
                                  className={`text-[9px] px-1 py-0.2 rounded font-extrabold transition-all ${
                                    isSubmitted
                                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                      : 'bg-slate-100 text-slate-400 border border-slate-200 border-dashed'
                                  }`}
                                >
                                  {doc.short}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      </td>

                      {/* AI Review Status */}
                      <td className="py-4 px-5">
                        {getStatusBadge(c.review_status, c.completeness_rate)}
                      </td>

                      {/* Created At */}
                      <td className="py-4 px-5 text-slate-500 font-semibold text-[11px]">
                        <div className="flex items-center space-x-1">
                          <Calendar className="w-3 h-3 text-slate-400 shrink-0" />
                          <span>{formatDate(c.created_at)}</span>
                        </div>
                      </td>

                      {/* Action Buttons */}
                      <td className="py-4 px-5 text-center">
                        <div className="flex items-center justify-center space-x-1.5">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectContract(c.contract_id);
                            }}
                            className="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-bold text-[11px] shadow-xs transition-all flex items-center space-x-1"
                            title="상세 서류 검수 워크스페이스 열기"
                          >
                            <span>검수/상세</span>
                            <ExternalLink className="w-3 h-3" />
                          </button>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onEditContract(c);
                            }}
                            className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900 rounded-lg transition-colors"
                            title="계약 정보 수정"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>

                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteContract(c.contract_id, c.title);
                            }}
                            className="p-1.5 bg-rose-50 hover:bg-rose-100 text-rose-600 hover:text-rose-800 rounded-lg transition-colors"
                            title="계약 삭제"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Footer Count */}
        <div className="px-5 py-3.5 bg-slate-50/80 border-t border-slate-200/80 flex items-center justify-between text-xs text-slate-500">
          <span className="font-semibold">
            총 {totalCount}개 계약 중 {filteredContracts.length}개 표시
          </span>
          <span className="text-[11px] text-slate-400">
            행을 클릭하면 해당 계약의 6종 서류 체크리스트 및 AI 검수 화면으로 이동합니다.
          </span>
        </div>
      </div>
    </div>
  );
};
