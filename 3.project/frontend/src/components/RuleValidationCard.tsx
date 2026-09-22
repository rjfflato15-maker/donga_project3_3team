import React from 'react';
import { ValidationCheck, ValidationStatus } from '../types';
import { CheckCircle, AlertTriangle, XCircle, Info, ShieldCheck } from 'lucide-react';

interface RuleValidationCardProps {
  checks: ValidationCheck[];
}

export const RuleValidationCard: React.FC<RuleValidationCardProps> = ({ checks }) => {
  const getStatusIcon = (status: ValidationStatus) => {
    switch (status) {
      case 'PASS':
        return <CheckCircle className="w-5 h-5 text-emerald-500 shrink-0" />;
      case 'FAIL':
        return <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />;
      case 'MISSING':
        return <XCircle className="w-5 h-5 text-rose-500 shrink-0" />;
      case 'REVIEW':
      default:
        return <Info className="w-5 h-5 text-blue-500 shrink-0" />;
    }
  };

  const getStatusBadge = (status: ValidationStatus) => {
    switch (status) {
      case 'PASS':
        return (
          <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
            일치 (PASS)
          </span>
        );
      case 'FAIL':
        return (
          <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
            불일치 (FAIL)
          </span>
        );
      case 'MISSING':
        return (
          <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
            누락 (MISSING)
          </span>
        );
      case 'REVIEW':
      default:
        return (
          <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
            검토 (REVIEW)
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 p-6 shadow-sm">
      <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-bold text-slate-900">AI / RULE 검수 결과</h2>
        </div>
        <span className="text-xs text-slate-400 font-medium">결정론적 교차검증</span>
      </div>

      <div className="space-y-3">
        {checks.map((check, idx) => {
          const isError = check.status === 'FAIL' || check.status === 'MISSING';

          return (
            <div
              key={idx}
              className={`p-4 rounded-xl border transition-all ${
                isError
                  ? check.status === 'FAIL'
                    ? 'bg-amber-50/40 border-amber-200/80'
                    : 'bg-rose-50/40 border-rose-200/80'
                  : 'bg-slate-50/50 border-slate-200/70'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start space-x-3">
                  {getStatusIcon(check.status)}
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-slate-900">
                        {check.rule_id === 'BUSINESS_NO_MATCH' && '사업자번호 일치'}
                        {check.rule_id === 'BUSINESS_STATUS' && '계속사업자 / 사업상태'}
                        {check.rule_id === 'AMOUNT_MATCH_TAX_INVOICE' && '금액 불일치 (세금계산서)'}
                        {check.rule_id === 'AMOUNT_MATCH_ESTIMATE' && '금액 대조 (견적서)'}
                        {check.rule_id === 'REQUIRED_DOCUMENTS' && '필수 증빙 누락'}
                      </span>
                      {getStatusBadge(check.status)}
                    </div>
                    <p className="text-xs font-medium text-slate-700 mt-1">
                      {check.message}
                    </p>

                    {(check.expected || check.actual) && (
                      <div className="mt-2.5 pt-2 border-t border-slate-200/60 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-600">
                        {check.expected && (
                          <span>기준값: <strong className="text-slate-800">{check.expected}</strong></span>
                        )}
                        {check.actual && (
                          <span>추출값: <strong className={isError ? 'text-rose-600 font-bold' : 'text-slate-800'}>{check.actual}</strong></span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
