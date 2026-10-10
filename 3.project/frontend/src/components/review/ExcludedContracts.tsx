import {useState} from 'react';
import {requestJson} from '../../api/client';
import {useAuth} from '../../context/AuthContext';
import {maskVendorName} from '../../utils/masking';

interface Excluded {contract_id:number;title:string;vendor_name:string;excluded_at:string;excluded_by:string}
export function ExcludedContracts({masked,onOpen}:{masked:boolean;onOpen:(id:number)=>void}){
 const {user}=useAuth();
 const [rows,setRows]=useState<Excluded[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const canRestore=user?.role==='operator'||user?.role==='admin';
 const load=async()=>{setBusy(true);setError('');try{setRows(await requestJson<Excluded[]>('/api/contracts/excluded'));}catch(e){setError(e instanceof Error?e.message:'목록을 불러오지 못했습니다.');}finally{setBusy(false);}};
 const restore=async(id:number)=>{setBusy(true);setError('');try{await requestJson(`/api/contracts/${id}/restore`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note:'업무함에서 다시 처리하기 위해 복원'})});setRows(old=>old.filter(r=>r.contract_id!==id));onOpen(id);}catch(e){setError(e instanceof Error?e.message:'복원하지 못했습니다.');}finally{setBusy(false);}};
 return <details className="surface record-memo" onToggle={e=>{if(e.currentTarget.open)void load();}}><summary>제외한 계약 보기</summary>
  {error&&<p role="alert" className="story-alert">{error}<button className="text-button" onClick={()=>void load()}>다시 불러오기</button></p>}
  {busy&&<p role="status">불러오는 중…</p>}
  {!busy&&!rows.length&&!error&&<p className="review-note">제외한 계약이 없습니다.</p>}
  {rows.map(row=><article key={row.contract_id} className="request-record"><strong>{row.title}</strong><p>계약 #{row.contract_id} · {maskVendorName(row.vendor_name,masked)} · {row.excluded_by} 제외</p>{canRestore&&<button className="button" disabled={busy} onClick={()=>void restore(row.contract_id)}>업무함으로 복원</button>}</article>)}
 </details>;
}
