import React, { useEffect, useState } from 'react';
import { X, Download, Shield, FileText, Save } from 'lucide-react';
import { DocumentResponse, AnalysisFields, DocumentType } from '../types';
import { api, downloadProtected, requestJson } from '../api/client';

export const documentLabels: Record<DocumentType, string> = {
  contract: '계약서', estimate: '견적서', business_registration: '사업자등록증',
  bank_account: '통장사본', tax_invoice: '세금계산서', inspection_confirmation: '검수확인서', unknown: '미분류',
};
const inputStyle = 'mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm';
const numericFields = ['amount', 'supply_amount', 'tax_amount', 'total_amount'] as const;

export const PilotDocumentDialog: React.FC<{
  doc: DocumentResponse; revision: number; canEdit: boolean; onClose: () => void; onChanged: () => Promise<void>;
}> = ({ doc, revision, canEdit, onClose, onChanged }) => {
  const [tab, setTab] = useState<'preview' | 'fields'>('preview');
  const [masked, setMasked] = useState(true);
  const [page, setPage] = useState(0);
  const [pages, setPages] = useState(1);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  const [previewText, setPreviewText] = useState('');
  const [imageError, setImageError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [fields, setFields] = useState<AnalysisFields>(doc.analysis.fields);
  const [dtype, setDtype] = useState<DocumentType>(doc.document_type);
  const [note, setNote] = useState('');
  const isPdf = /\.pdf$/i.test(doc.original_file_name);
  const isImage = /\.(png|jpe?g|webp|bmp|gif|tiff?)$/i.test(doc.original_file_name);
  const visual = isPdf || isImage;
  useEffect(() => {
    setFields(doc.analysis.fields); setDtype(doc.document_type); setNote('');
  }, [doc.document_id, revision]);
  useEffect(() => {
    setPage(0); setPages(1);
    if (!doc.file_available || !isPdf) return;
    const controller = new AbortController();
    requestJson<{ total_pages: number }>('/api/documents/' + doc.document_id + '/pages-info', { signal: controller.signal })
      .then(value => setPages(value.total_pages))
      .catch(reason => { if (!controller.signal.aborted) setImageError(reason.message); });
    return () => controller.abort();
  }, [doc.document_id, doc.file_available, isPdf]);
  useEffect(() => {
    setImageLoaded(false); setImageError(''); setImageUrl('');
    if (!doc.file_available || !visual || tab !== 'preview') return;
    const controller = new AbortController();
    let active = true;
    let url = '';
    const timeout = window.setTimeout(() => controller.abort(), 30_000);
    fetch('/api/documents/' + doc.document_id + '/preview-image?page=' + page + '&masked=' + masked + '&revision=' + revision, { credentials: 'same-origin', signal: controller.signal })
      .then(async response => {
        if (!response.ok) {
          if (response.status === 401) window.dispatchEvent(new Event('session-expired'));
          const body = await response.json().catch(() => ({}));
          throw new Error(body.detail || '미리보기를 생성하지 못했습니다.');
        }
        return response.blob();
      }).then(blob => { if (active) { url = URL.createObjectURL(blob); setImageUrl(url); } })
      .catch(reason => { if (active) setImageError(controller.signal.aborted ? '미리보기 생성이 30초를 넘었습니다. 다시 열거나 원본을 내려받아 확인하세요.' : reason.message); })
      .finally(() => window.clearTimeout(timeout));
    return () => { active = false; window.clearTimeout(timeout); controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [doc.document_id, doc.file_available, revision, visual, page, masked, tab]);
  useEffect(() => {
    setPreviewText('');
    if (!doc.file_available || visual || tab !== 'preview') return;
    const controller = new AbortController();
    requestJson<{ text: string }>('/api/documents/' + doc.document_id + '/text-preview?masked=' + masked, { signal: controller.signal })
      .then(value => setPreviewText(value.text))
      .catch(reason => { if (!controller.signal.aborted) setPreviewText(reason.message); });
    return () => controller.abort();
  }, [doc.document_id, doc.file_available, revision, visual, masked, tab]);
  const act = async (operation: () => Promise<void>) => {
    setBusy(true); setError('');
    try { await operation(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : '요청을 완료하지 못했습니다.'); }
    finally { setBusy(false); }
  };
  const save = (event: React.FormEvent) => {
    event.preventDefault();
    void act(async () => { await api.correctFields(doc.document_id, fields, dtype, revision, note); await onChanged(); });
  };
  const restore = (file?: File) => {
    if (!file) return;
    void act(async () => { await api.restoreOriginal(doc.document_id, file); await onChanged(); });
  };
  const download = (mask: boolean) => void act(() => downloadProtected('/api/documents/' + doc.document_id + '/download?masked=' + mask, doc.original_file_name));
  return <div className="fixed inset-0 z-50 bg-slate-900/60 p-3 sm:p-6 flex items-center justify-center">
    <section role="dialog" aria-modal="true" aria-labelledby="pilot-doc-title" className="bg-white rounded-2xl shadow-xl w-full max-w-5xl max-h-[92vh] overflow-y-auto">
      <header className="p-5 border-b flex justify-between gap-4">
        <div className="min-w-0"><h2 id="pilot-doc-title" className="font-bold text-lg break-all">{doc.original_file_name}</h2><p className="text-sm text-slate-500">{documentLabels[doc.document_type]} · 문서분류 참고점수 {Math.round(doc.confidence * 100)}% · 실제 정확도 측정값은 아닙니다.</p></div>
        <button aria-label="닫기" onClick={onClose} className="p-2 self-start rounded-lg hover:bg-slate-100"><X size={22} /></button>
      </header>
      <div className="p-5 space-y-4">
        <div className="flex gap-2 flex-wrap">
          <button onClick={() => setTab('preview')} className={'rounded-lg px-4 py-2 text-sm ' + (tab === 'preview' ? 'bg-indigo-600 text-white' : 'bg-slate-100')}>문서 미리보기</button>
          <button onClick={() => setTab('fields')} className={'rounded-lg px-4 py-2 text-sm ' + (tab === 'fields' ? 'bg-indigo-600 text-white' : 'bg-slate-100')}>{canEdit ? '추출값 확인·수정' : '추출값 확인'}</button>
          <button disabled={!doc.file_available || busy} onClick={() => download(false)} className="ml-auto flex items-center gap-2 border rounded-lg px-3 py-2 text-sm disabled:opacity-40"><Download size={16} />원본 다운로드</button>
          <button disabled={!doc.file_available || busy} onClick={() => download(true)} className="flex items-center gap-2 border rounded-lg px-3 py-2 text-sm disabled:opacity-40"><Shield size={16} />{visual ? '마스킹본 다운로드' : '마스킹 텍스트 다운로드'}</button>
        </div>
        {error && <p role="alert" className="rounded-lg bg-red-50 text-red-800 p-3 text-sm">{error}</p>}
        {!doc.file_available && <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 space-y-3">
          <h3 className="font-bold text-amber-900">공용 서버에 원본이 없습니다.</h3>
          <p className="text-sm text-amber-900">등록 정보와 추출값은 남아 있습니다. 담당자가 원본을 다시 등록하면 다른 컴퓨터에서도 미리보기와 다운로드가 가능합니다.</p>
          {canEdit && <label className="inline-flex bg-white border rounded-lg p-3 text-sm">원본 다시 등록<input disabled={busy} type="file" className="ml-3 max-w-full" onChange={e => { restore(e.target.files?.[0]); e.target.value = ''; }} /></label>}
          {canEdit && <p className="text-sm text-amber-900">재등록하면 문서를 다시 분석하며, 이전 대표 확인은 재확인 대상으로 바뀝니다.</p>}
        </div>}
        {tab === 'preview' && doc.file_available && <>
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 p-3 rounded-lg">
            <button onClick={() => setMasked(value => !value)} className="border rounded-lg px-3 py-2 text-sm flex gap-2 items-center"><Shield size={16} />{masked ? '자동 마스킹 보기' : '원본 보기'}</button>
            <span className="text-sm text-slate-600">자동 마스킹에는 누락이 있을 수 있습니다. 원본 열람과 다운로드는 기록됩니다.</span>
          </div>
          {visual ? <>
            <div className="bg-slate-100 rounded-xl p-3 text-center min-h-[240px]">
              {!imageLoaded && !imageError && <p role="status" className="p-6 text-slate-600">미리보기 생성 중…</p>}
              {imageError ? <p role="alert" className="p-6 text-red-800">{imageError} 원본 보기 또는 다운로드로 확인하세요.</p> : imageUrl &&
                <img key={doc.document_id + ':' + page + ':' + masked + ':' + revision}
                  src={imageUrl}
                  alt={doc.original_file_name + ' ' + (page + 1) + '페이지'}
                  onLoad={() => setImageLoaded(true)}
                  onError={() => { setImageLoaded(true); setImageError('미리보기를 만들지 못했습니다. 마스킹 실패 시 원본을 자동으로 표시하지 않습니다.'); }}
                  className={'mx-auto max-w-full max-h-[70vh] object-contain ' + (!imageLoaded ? 'hidden' : '')} />}
            </div>
            {isPdf && <div className="flex items-center justify-center gap-4 text-sm"><button disabled={page === 0} onClick={() => setPage(value => value - 1)} className="border rounded-lg px-3 py-2 disabled:opacity-40">이전</button><span>{page + 1} / {pages} 페이지</span><button disabled={page + 1 >= pages} onClick={() => setPage(value => value + 1)} className="border rounded-lg px-3 py-2 disabled:opacity-40">다음</button></div>}
          </> : <div><p className="text-sm text-slate-600 mb-3">Word·한글·엑셀은 추출 텍스트를 미리 보여줍니다. 원본 서식은 다운로드한 파일로 확인하세요.</p><pre className="p-4 bg-slate-50 rounded-lg whitespace-pre-wrap break-words text-sm">{previewText || '텍스트 미리보기 불러오는 중…'}</pre></div>}
        </>}
        {tab === 'fields' && <form onSubmit={save} className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-4">
            <label className="text-sm">문서 유형<select disabled={!canEdit} value={dtype} onChange={e => setDtype(e.target.value as DocumentType)} className={inputStyle}>{Object.entries(documentLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
            <label className="text-sm">업체명<input disabled={!canEdit} value={fields.company_name || ''} onChange={e => setFields(prev => ({ ...prev, company_name: e.target.value }))} className={inputStyle} /></label>
            <label className="text-sm">사업자등록번호<input disabled={!canEdit} value={fields.business_registration_no || ''} onChange={e => setFields(prev => ({ ...prev, business_registration_no: e.target.value }))} className={inputStyle} /></label>
            <label className="text-sm">발행일<input disabled={!canEdit} value={fields.issue_date || ''} onChange={e => setFields(prev => ({ ...prev, issue_date: e.target.value }))} className={inputStyle} /></label>
            {numericFields.map((key, index) => <label key={key} className="text-sm">{['기존 추출 금액', '공급가액', '세액', '합계'][index]}<input disabled={!canEdit} min="0" step="1" type="number" value={fields[key] ?? ''} onChange={e => setFields(prev => ({ ...prev, [key]: e.target.value === '' ? null : Number(e.target.value) }))} className={inputStyle} /></label>)}
            <label className="text-sm">기존 추출 금액의 의미<select disabled={!canEdit} value={fields.amount_basis || 'UNKNOWN'} onChange={e => setFields(prev => ({ ...prev, amount_basis: e.target.value as AnalysisFields['amount_basis'] }))} className={inputStyle}><option value="UNKNOWN">확인 필요</option><option value="TOTAL">부가세 포함 합계</option><option value="SUPPLY">공급가액</option></select></label>
            <label className="text-sm">청구 범위<select disabled={!canEdit} value={fields.amount_scope || 'UNKNOWN'} onChange={e => setFields(prev => ({ ...prev, amount_scope: e.target.value as AnalysisFields['amount_scope'] }))} className={inputStyle}><option value="UNKNOWN">확인 필요</option><option value="FULL">전체 청구</option><option value="PARTIAL">부분 청구</option></select></label>
          </div>
          {canEdit && <><label className="block text-sm">수정 근거<textarea required maxLength={1000} value={note} onChange={e => setNote(e.target.value)} placeholder="예: 세금계산서 1페이지 합계란을 확인함" className={inputStyle} /></label><button disabled={busy} className="flex gap-2 items-center bg-indigo-600 text-white rounded-lg px-4 py-2 disabled:opacity-40"><Save size={16} />저장하고 재검수</button></>}
          {!canEdit && <p className="text-sm text-slate-600"><FileText className="inline mr-1" size={16} />추출값 수정은 담당자에게 요청하세요.</p>}
        </form>}
      </div>
    </section>
  </div>;
};
