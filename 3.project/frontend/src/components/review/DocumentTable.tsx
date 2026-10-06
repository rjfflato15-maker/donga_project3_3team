import { DOCUMENT_LABEL as DOCUMENT_TYPE_KO } from '../../utils/documentLabels';
import React, { useEffect, useState } from 'react';
import { FileText, ArrowUpRight, Plus } from 'lucide-react';
import { ContractDetail, DocumentResponse, DocumentType } from '../../types';
import { requestJson } from '../../api/client';
import { isUnverifiedBusinessStatus } from '../../utils/reviewSummary';
import { fieldsForDocument } from '../../utils/documentFields';
import { Surface, Badge } from '../ui/Surface';
type ConfirmationFields = Record<string, { value: unknown; human_confirmation?: unknown }>;
export function confirmationCount(fields: ConfirmationFields) {
  const values = Object.values(fields).filter((f) => f.value != null && f.value !== '' && f.value !== 'UNKNOWN');
  return { total: values.length, confirmed: values.filter((f) => f.human_confirmation).length };
}
export const DocumentTable: React.FC<{ contract: ContractDetail; canEdit: boolean; onOpen: (d:DocumentResponse) => void; onUpload:(type?:DocumentType) => void }> = ({ contract, canEdit, onOpen, onUpload }) => {
  const [confirmation, setConfirmation] = useState<Record<number, ReturnType<typeof confirmationCount>>>({});
  const [failures, setFailures] = useState<Set<number>>(new Set());
  useEffect(() => {
    const abort = new AbortController(); setConfirmation({});setFailures(new Set());
    void Promise.allSettled(contract.documents.map(async (doc) => {
      try {
      const p = await requestJson<{ fields: ConfirmationFields }>(`/api/documents/${doc.document_id}/provenance`, { signal: abort.signal });
      if (!abort.signal.aborted) setConfirmation((old) => ({ ...old, [doc.document_id]: confirmationCount(Object.fromEntries(fieldsForDocument(doc.document_type).filter((f) => p.fields[f.key]).map((f) => [f.key,p.fields[f.key]]))) }));
      } catch { if (!abort.signal.aborted) setFailures((old) => new Set(old).add(doc.document_id)); }
    }));
    return () => abort.abort();
  }, [contract.contract_id, contract.workflow?.revision]);
  const docs = contract.documents.filter((d) => d.version?.is_current !== false);
  const visibleDocs = [...docs].sort((a,b)=>contract.required_document_types.indexOf(a.document_type)-contract.required_document_types.indexOf(b.document_type));
  const missing = contract.required_document_types.filter((t) => !docs.some((d) => d.document_type === t));
  return <Surface title="서류 목록" sub={`필요 ${contract.required_document_types.length}종 · 받은 ${contract.required_document_types.length - missing.length}종`} action={canEdit && <button className="button" onClick={() => onUpload()}><Plus size={15} />서류 추가</button>}>
    <div className="table-wrap"><table className="documents"><thead><tr><th>서류</th><th>현재 본</th><th>검사</th><th>원문 확인</th><th /></tr></thead><tbody>
      {[...contract.required_document_types.flatMap<{doc:DocumentResponse|null;type:DocumentType}>(type=>{const same=visibleDocs.filter(d=>d.document_type===type);return same.length?same.map(d=>({doc:d,type})): [{doc:null,type}];}),...visibleDocs.filter(d=>!contract.required_document_types.includes(d.document_type)).map(doc=>({doc,type:doc.document_type}))].map(({doc:d,type},index)=>{
        if(!d)return <tr key={`missing-${type}`}><td><span className="doc-name"><FileText size={17}/>{DOCUMENT_TYPE_KO[type]}</span></td><td>—</td><td><Badge tone="amber">미제출</Badge></td><td>—</td><td>{canEdit&&<button className="text-button" onClick={()=>onUpload(type)}>파일 올리기<Plus size={14}/></button>}</td></tr>;
        const checks=contract.checks.filter(c=>c.field===String(d.document_id)&&!isUnverifiedBusinessStatus(c));
        const label=!d.file_available?'원본 없음':checks.some(c=>c.status==='FAIL')?'불일치':checks.some(c=>c.status!=='PASS')?'확인 필요':checks.length?'적용 검사 일치':'검사 없음';
        const counts=confirmation[d.document_id];
        return <tr key={`${d.document_id}-${index}`}><td><span className="doc-name" title={d.original_file_name}><FileText size={17}/>{DOCUMENT_TYPE_KO[d.document_type]}</span></td><td>{d.version?.version_number??1}번째 본</td><td><Badge tone={label==='적용 검사 일치'?'green':label==='불일치'||label==='원본 없음'?'red':label==='검사 없음'?'gray':'amber'}>{label}</Badge></td><td><small>{counts?counts.total?`${counts.confirmed}/${counts.total}값 확인`:'—':failures.has(d.document_id)?'조회 실패':'조회 중'}</small></td><td><button className="text-button" onClick={()=>onOpen(d)}>원문 대조<ArrowUpRight size={14}/></button></td></tr>;
      })}
    </tbody></table></div>
  </Surface>;
};
