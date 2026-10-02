import React, { useMemo, useState } from 'react';
import { ContractDetail } from '../../types';
import { IssueGroup, DOCUMENT_TYPE_KO } from '../../utils/reviewSummary';
import { X } from 'lucide-react';
import { followUpApi, ContactMethod, CONTACT_KO } from '../../api/followUp';

interface Props {
  contract: ContractDetail;
  issue: IssueGroup;
  isMaskingEnabled: boolean;
  canRecord: boolean;
  onClose: () => void;
  onRecorded: () => Promise<void> | void;
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

export const RequestDraftDialog: React.FC<Props> = ({ contract, issue, canRecord, onClose, onRecorded }) => {
  const drafts = useMemo(() => buildDrafts(contract, issue), [contract, issue]);
  const [mode, setMode] = useState<'short' | 'long'>('short');
  const [text, setText] = useState(drafts.short);
  const [copied, setCopied] = useState<string>('');
  const [method, setMethod] = useState<ContactMethod>('KAKAO');
  const [due, setDue] = useState('');
  const [busy, setBusy] = useState(false);
  const [recordError, setRecordError] = useState('');

  const record = async () => {
    setBusy(true); setRecordError('');
    try {
      const reason = issue.checks.map((c) => c.message.replace(/^[^:]+:\s*/, '')).join(' ');
      await followUpApi.record(contract.contract_id, {
        contact_method: method,
        due_on: due || null,
        memo: `${issue.title}: ${reason}`.slice(0, 2000),
      });
      await onRecorded();
      onClose();
    } catch (e) {
      setRecordError(e instanceof Error ? e.message : '기록하지 못했습니다.');
    } finally {
      setBusy(false);
    }
  };

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
          <p className="text-xs text-slate-500">앱은 메시지를 직접 보내지 않습니다. 평소 쓰는 방법으로 보낸 뒤 아래에서 기록해 주세요.</p>
          {canRecord && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2">
              <div className="text-sm font-semibold text-slate-800">보냈다면 기록하기</div>
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="grid gap-1 text-xs text-slate-600">어떻게 요청했나요?
                  <select value={method} onChange={(e) => setMethod(e.target.value as ContactMethod)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800">
                    {(Object.keys(CONTACT_KO) as ContactMethod[]).map((m) => <option key={m} value={m}>{CONTACT_KO[m]}</option>)}
                  </select>
                </label>
                <label className="grid gap-1 text-xs text-slate-600">회신 기한 (선택)
                  <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800" />
                </label>
              </div>
              <button onClick={record} disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">
                {busy ? '기록 중…' : '요청했어요 · 기록하기'}
              </button>
              {recordError && <p className="text-xs text-rose-600">{recordError}</p>}
              <p className="text-[11px] text-slate-500">기록하면 이 계약이 '회신 대기'로 표시됩니다. 언제·어떻게 요청했는지만 남기고, 메시지 내용은 저장하지 않습니다.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
