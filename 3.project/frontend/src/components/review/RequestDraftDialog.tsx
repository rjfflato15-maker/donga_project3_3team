import React, { useMemo, useState } from 'react';
import { ContractDetail } from '../../types';
import { IssueGroup, DOCUMENT_TYPE_KO } from '../../utils/reviewSummary';
import { X } from 'lucide-react';

interface Props {
  contract: ContractDetail;
  issue: IssueGroup;
  isMaskingEnabled: boolean;
  onClose: () => void;
}

const AMOUNT_RULES = new Set(['AMOUNT_COMPONENTS', 'AMOUNT_MATCH_TAX_INVOICE', 'PAYMENT_SCOPE', 'INSTALLMENT_TOTAL']);

function buildDrafts(contract: ContractDetail, issue: IssueGroup) {
  const vendor = contract.vendor_name;
  const docName = issue.document ? DOCUMENT_TYPE_KO[issue.document.document_type] : issue.missingType ? DOCUMENT_TYPE_KO[issue.missingType] : '서류';
  const isTaxInvoiceAmount =
    issue.document?.document_type === 'tax_invoice' && issue.checks.some((c) => AMOUNT_RULES.has(c.rule_id));
  const reasons = issue.checks.map((c) => c.message.replace(/^[^:]+:\s*/, '')).join(' ');

  let ask: string;
  if (issue.missingType) ask = `${docName}을(를) 보내 주시기 바랍니다.`;
  else if (isTaxInvoiceAmount) ask = '홈택스에서 수정 세금계산서를 발행해 주시기 바랍니다.';
  else ask = `${docName}을(를) 확인하시어 다시 보내 주시기 바랍니다.`;

  const short = issue.missingType
    ? `[${vendor}] '${contract.title}' 계약 증빙 중 ${docName}이(가) 아직 없어요. ${ask}`
    : `[${vendor}] '${contract.title}' 계약 ${docName} 확인 결과: ${reasons} ${ask}`;

  const long = [
    `${vendor} 담당자님, 안녕하세요.`,
    '',
    `「${contract.title}」 계약의 증빙 서류를 확인한 결과를 알려 드립니다.`,
    issue.missingType ? `- ${docName}이(가) 제출되지 않았습니다.` : issue.checks.map((c) => `- ${c.message}`).join('\n'),
    '',
    ask,
    '감사합니다.',
  ].join('\n');
  return { short, long };
}

export const RequestDraftDialog: React.FC<Props> = ({ contract, issue, onClose }) => {
  const drafts = useMemo(() => buildDrafts(contract, issue), [contract, issue]);
  const [mode, setMode] = useState<'short' | 'long'>('short');
  const [text, setText] = useState(drafts.short);
  const [copied, setCopied] = useState<string>('');

  const switchMode = (next: 'short' | 'long') => {
    setMode(next);
    setText(drafts[next]);
    setCopied('');
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied('복사했습니다. 카카오톡·문자·이메일에 붙여 넣으세요.');
    } catch {
      setCopied('복사하지 못했습니다. 글을 선택해 Ctrl+C로 복사하세요.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="draft-title">
      <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl">
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
          <h2 id="draft-title" className="font-bold text-slate-900">재제출 요청 문구</h2>
          <span className="text-xs text-slate-500">{issue.title}</span>
          <button onClick={onClose} className="ml-auto rounded-lg p-1 text-slate-400 hover:bg-slate-100" aria-label="닫기">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div className="inline-flex rounded-lg border border-slate-200 p-0.5 text-xs" role="tablist">
            <button role="tab" aria-selected={mode === 'short'} onClick={() => switchMode('short')}
              className={`rounded-md px-3 py-1.5 font-semibold ${mode === 'short' ? 'bg-indigo-600 text-white' : 'text-slate-600'}`}>
              짧게 (카톡·문자)
            </button>
            <button role="tab" aria-selected={mode === 'long'} onClick={() => switchMode('long')}
              className={`rounded-md px-3 py-1.5 font-semibold ${mode === 'long' ? 'bg-indigo-600 text-white' : 'text-slate-600'}`}>
              자세히 (이메일)
            </button>
          </div>
          <label htmlFor="draft-text" className="sr-only">요청 문구</label>
          <textarea
            id="draft-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="h-48 w-full rounded-xl border border-slate-200 bg-white p-3 text-sm leading-relaxed text-slate-800"
          />
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={copy} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">문구 복사</button>
            <span className="text-xs text-slate-500">{copied}</span>
          </div>
          <p className="text-xs text-slate-500">
            앱은 메시지를 직접 보내지 않습니다. 평소 쓰는 방법으로 보내 주세요. 요청 기록(연락 방법·기한)과 '회신 대기' 상태는 다음 단계에서 연결됩니다.
          </p>
        </div>
      </div>
    </div>
  );
};
