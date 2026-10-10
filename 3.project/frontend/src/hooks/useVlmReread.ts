import { useEffect, useRef, useState } from 'react';
import { requestJson } from '../api/client';
import { fieldsForDocument } from '../utils/documentFields';

export interface VlmCandidate { field: string; value: string | number | null; quote: string; usable: boolean; reason: string; changed?: boolean }
export interface VlmResult { run_id: number; page: number; model: {name:string}; created_at: string; candidates: VlmCandidate[] }
interface Status { ready: boolean; model: string | null; message: string }
interface Props { documentId:number; documentType:string; revision:number; page:number; masked:boolean; enabled:boolean }

export function useVlmReread({documentId,documentType,revision,page,masked,enabled}:Props) {
  const [status,setStatus] = useState<Status|null>(null), [result,setResult] = useState<VlmResult|null>(null);
  const [busy,setBusy] = useState(false), [error,setError] = useState(''), [reload,setReload] = useState(0);
  const generation = useRef(0), active = useRef<AbortController|null>(null);
  useEffect(() => {
    const token = ++generation.current, controller = new AbortController();
    active.current?.abort(); setResult(null); setStatus(null); setError(''); setBusy(false);
    if (enabled) void Promise.all([
      requestJson<Status>('/api/vlm/status',{signal:controller.signal}),
      requestJson<VlmResult|null>(`/api/documents/${documentId}/vlm-reread?revision=${revision}&masked=${masked}`,{signal:controller.signal}),
    ]).then(([info,previous])=>{if(!controller.signal.aborted && token===generation.current){setStatus(info);setResult(previous?.page===page?previous:null);}})
      .catch(reason=>{if(!controller.signal.aborted&&token===generation.current)setError(reason.message);});
    return ()=>{generation.current++;controller.abort();active.current?.abort();};
  },[documentId,revision,page,masked,enabled,reload]);
  const reread = async (requestedFields?:string[]) => {
    if (!enabled || !status?.ready || busy) return false;
    const token=++generation.current,controller=new AbortController(); active.current=controller;
    setBusy(true);setError('');setResult(null);
    try {
      const value=await requestJson<VlmResult>(`/api/documents/${documentId}/vlm-reread?masked=${masked}`,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
        body:JSON.stringify({revision,page,fields:requestedFields?.length?requestedFields:fieldsForDocument(documentType).map(field=>field.key)})});
      if(!controller.signal.aborted&&token===generation.current){setResult(value);return true;}
    } catch(reason){if(!controller.signal.aborted&&token===generation.current)setError(reason instanceof Error?reason.message:'다시 읽지 못했습니다.');}
    finally{if(token===generation.current)setBusy(false);}
    return false;
  };
  return {status,result,busy,error,reread,refresh:()=>setReload(value=>value+1)};
}
