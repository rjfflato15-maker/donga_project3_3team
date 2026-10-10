
import {useEffect,useRef,useState} from 'react';
import {FileText,Upload,ArrowLeft,ArrowRight,Loader2,X} from 'lucide-react';
import {api} from '../api/client';
import {DocumentType,AutoContractSynthesisResponse} from '../types';
import {Badge,Surface} from './ui/Surface';
const SLOTS:[DocumentType,string][]=[['contract','계약서'],['estimate','견적서'],['business_registration','사업자등록증'],['bank_account','통장사본'],['tax_invoice','세금계산서'],['inspection_confirmation','검수확인서']];
export function CompareRegistration({onClose,onSuccess}:{onClose:()=>void;onSuccess:(id:number)=>Promise<void>}){
 const [step,setStep]=useState<'files'|'basis'>('files'),[files,setFiles]=useState<Partial<Record<DocumentType,File>>>({}),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [draft,setDraft]=useState({title:'',vendor_name:'',business_number:'',contract_amount:'',amount_basis:'TOTAL',tax_amount:'',payment_mode:'FULL'});
 const [parsed,setParsed]=useState<AutoContractSynthesisResponse|null>(null),[created,setCreated]=useState<number|null>(null);
 const [requestKey]=useState(()=>typeof crypto!=='undefined'&&typeof crypto.randomUUID==='function'?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`),[partial,setPartial]=useState(false);
 const [fileUrls,setFileUrls]=useState<Partial<Record<DocumentType,string>>>({});
 useEffect(()=>{const urls:Partial<Record<DocumentType,string>>={};for(const [kind,file] of Object.entries(files)){if(file)urls[kind as DocumentType]=URL.createObjectURL(file);}setFileUrls(urls);return()=>{Object.values(urls).forEach(url=>URL.revokeObjectURL(url));};},[files]);
 const input=useRef<HTMLInputElement>(null),slot=useRef<DocumentType>('contract'),alive=useRef(true),heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 useEffect(()=>{heading.current?.focus();},[step]);
 // Both arrays must come from the same slot-ordered pairs, never object insertion order.
 const selectedPairs=SLOTS.flatMap(([kind])=>files[kind]?[{kind,file:files[kind]!}]:[]);
 const selected=selectedPairs.map(({file})=>file);
 const read=async()=>{if(!selected.length)return;setBusy(true);setError('');try{const result=await api.autoParseBatchDocuments(selected);if(!alive.current)return;setParsed(result);setDraft(d=>({...d,title:result.title||'',vendor_name:result.vendor_name||'',business_number:result.business_number||'',contract_amount:result.contract_amount?.toString()||''}));setStep('basis');}catch(e){if(alive.current){setError('서류 내용을 읽지 못했습니다. 계약 기준을 직접 입력해 주세요.');setStep('basis');}}finally{if(alive.current)setBusy(false);}};
 const submit=async()=>{
  if(created&&!partial)return;
  if(!draft.title.trim()||!draft.vendor_name.trim()||!draft.business_number.trim()||!draft.contract_amount||!Number.isFinite(Number(draft.contract_amount))||Number(draft.contract_amount)<=0){setError('계약명·거래처·사업자번호·양수인 계약 금액을 입력해 주세요.');return;}
  if(draft.amount_basis==='SUPPLY'&&(draft.tax_amount===''||Number(draft.tax_amount)<0)){setError('공급가액 기준이면 계약서에 적힌 세액을 입력해 주세요.');return;}
  setBusy(true);setError('');
  try{
   const c=await api.autoCreateBatchContract({title:draft.title.trim(),vendor_name:draft.vendor_name.trim(),business_number:draft.business_number.trim(),contract_amount:Number(draft.contract_amount),amount_basis:draft.amount_basis,tax_amount:draft.amount_basis==='SUPPLY'?Number(draft.tax_amount):null,payment_mode:draft.payment_mode},selected,{documentTypes:selectedPairs.map(({kind})=>kind),requestKey});
   if(!alive.current)return;
   setCreated(c.contract_id);
   const incomplete=c.registration?.complete===false;setPartial(incomplete);
   if(incomplete){setError(`계약 #${c.contract_id}은 등록됐어요. ${c.registration!.failed_files.map(f=>f.file_name||f.message).join(', ')} 처리를 다시 시도하거나 계약 화면에서 보완하세요.`);return;}
   await onSuccess(c.contract_id);
  }catch(e){if(alive.current)setError(e instanceof Error?e.message:'계약 등록 실패');}
  finally{if(alive.current)setBusy(false);}
 };
 return <><button className="back" disabled={busy} onClick={onClose}><ArrowLeft size={15}/>업무함</button><div className="contract-heading"><div><small className="eyebrow">계약 등록 전</small><div className="title-row"><h1>{draft.title||'새 계약 등록'}</h1><Badge>{step==='files'?'서류 선택':'기준 확인'}</Badge></div><div className="meta"><span>{draft.vendor_name||'거래처 미입력'}</span><span>등록 전</span></div></div><div className="contract-amount"><small>계약 금액 · {draft.amount_basis==='TOTAL'?'부가세 포함':'공급가액'}</small><strong>{draft.contract_amount?Number(draft.contract_amount).toLocaleString('ko-KR'):'—'}<span>원</span></strong><small>{draft.payment_mode==='FULL'?'일시 지급':'분할 지급'}</small></div></div><Surface title="새 계약 등록" sub={step==='files'?'1. 서류 선택':'2. 계약 기준 확인'} className="story-registration">
 {step==='files'?<div className="story-form"><h2 ref={heading} tabIndex={-1} className="sr-only">서류 선택</h2><div className="story-selected-files">{SLOTS.map(([kind,label])=><div key={kind}><FileText size={19}/><strong>{label}</strong><span title={files[kind]?.name}>{files[kind]?.name||'파일 선택 전'}</span><button className="text-button" disabled={busy} onClick={()=>{slot.current=kind;input.current?.click();}}>{files[kind]?'바꾸기':'선택'}</button>{files[kind]&&<button className="icon" aria-label={`${label} 선택 취소`} disabled={busy} onClick={()=>setFiles(old=>{const next={...old};delete next[kind];return next;})}><X size={14}/></button>}</div>)}</div><input ref={input} aria-label="계약 등록 파일" type="file" className="sr-only" tabIndex={-1} accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tiff,.tif,.gif,.txt,.docx,.doc,.hwp,.hwpx,.xlsx,.xls,.csv" onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(!f)return;if(f.size>20*1024*1024){setError('파일당 20MB까지 등록할 수 있습니다.');return;}setFiles(old=>({...old,[slot.current]:f}));setError('');}}/></div>:<div className="story-form"><h2 ref={heading} tabIndex={-1} className="sr-only">계약 기준 확인</h2><div className="story-selected-files">{SLOTS.map(([k,label])=><div key={k}><FileText size={19}/><strong>{label}</strong><span title={files[k]?.name}>{files[k]?.name||'아직 없음'}</span>{files[k]&&fileUrls[k]?<a className="text-button" aria-label={`${label} 원문 열기`} href={fileUrls[k]} target="_blank" rel="noopener noreferrer">원문 열기</a>:<Badge tone="amber">미선택</Badge>}</div>)}{parsed&&<small>읽어 온 값은 원문과 대조해 확인합니다.</small>}</div><div className="form-fields">{([['title','계약명'],['vendor_name','거래처'],['business_number','사업자등록번호'],['contract_amount','계약 금액 (원)']] as const).map(([key,label])=><label key={key}>{label}<input value={draft[key]} disabled={busy||!!created} type={key==='contract_amount'?'number':'text'} min={key==='contract_amount'?1:undefined} onChange={e=>setDraft({...draft,[key]:e.target.value})}/></label>)}<label>금액 기준<select value={draft.amount_basis} disabled={busy||!!created} onChange={e=>setDraft({...draft,amount_basis:e.target.value})}><option value="TOTAL">부가세 포함 합계</option><option value="SUPPLY">공급가액 (부가세 별도)</option></select></label>{draft.amount_basis==='SUPPLY'&&<label>세액 (원)<input type="number" min={0} value={draft.tax_amount} disabled={busy||!!created} onChange={e=>setDraft({...draft,tax_amount:e.target.value})}/></label>}<label>지급 방식<select value={draft.payment_mode} disabled={busy||!!created} onChange={e=>setDraft({...draft,payment_mode:e.target.value})}><option value="FULL">일시 지급</option><option value="INSTALLMENT">분할 지급</option></select></label></div></div>}
 {error&&<p className="story-alert" role="alert">{error}</p>}
 <div className="panel-footer"><span>{step==='files'?'서류를 선택한 뒤 계약 기준을 확인합니다.':'원문과 대조한 값을 계약 기준으로 등록합니다.'}</span><div className="story-button-row">{step==='basis'&&!created&&<button className="button" disabled={busy} onClick={()=>setStep('files')}><ArrowLeft size={14}/>서류 선택</button>}{created?<>{partial&&<button className="button" disabled={busy} onClick={()=>void submit()}>{busy?'처리 중…':'실패한 서류 다시 처리'}</button>}<button className="button primary" disabled={busy} onClick={()=>void onSuccess(created)}>등록한 계약 확인</button></>:<button className="button primary" disabled={busy||!selected.length} onClick={()=>void(step==='files'?read():submit())}>{busy?<Loader2 size={16} className="animate-spin"/>:<Upload size={16}/>} {busy?'처리 중…':step==='files'?`선택한 서류 ${selected.length}개로 계속`:'계약 등록'}<ArrowRight size={14}/></button>}</div></div>
 </Surface></>;
}
