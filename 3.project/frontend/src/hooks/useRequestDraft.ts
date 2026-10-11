import {useEffect, useMemo, useRef, useState} from 'react';
import {BundleContext} from '../features/requests/model';

type Selection = {snapshot:string; reviewed:boolean};
type Draft = Map<string, Selection>;
interface SavedDraft {
  version:1;
  revision:number;
  fingerprint:string;
  items:{key:string; reviewed:boolean}[];
}
const prefix = 'c-pilot:request-draft:v1:';
function read(key:string|null):SavedDraft|null {
  if(!key)return null;
  try {
    const value = JSON.parse(sessionStorage.getItem(key)||'null');
    if(value?.version!==1||!Number.isInteger(value.revision)||typeof value.fingerprint!=='string'||!Array.isArray(value.items))return null;
    if(value.items.length>100||!value.items.every((item:SavedDraft['items'][number])=>typeof item?.key==='string'&&typeof item.reviewed==='boolean'))return null;
    return value;
  } catch {return null;}
}
const matches = (saved:SavedDraft, context:BundleContext)=>saved.revision===context.revision&&saved.fingerprint===context.fingerprint;
function restore(saved:SavedDraft|null, context:BundleContext|null):Draft {
  if(!saved||!context||!matches(saved,context))return new Map();
  return new Map(saved.items.flatMap(item=>{
    const candidate=context.vendor_candidates.find(candidate=>candidate.issue_key===item.key&&!candidate.already_requested);
    return candidate?[[item.key,{snapshot:JSON.stringify(candidate.snapshot??candidate.reason),reviewed:item.reviewed}] as const]:[];
  }));
}

/** Preserve selections in this tab; do not persist document values or request text. */
export function useRequestDraft(userId:number|undefined, contractId:number, context:BundleContext|null) {
  const scope=`${prefix}${userId??'memory'}:${contractId}`;
  const storageKey=userId==null?null:scope;
  const [state,setState]=useState(()=>({scope,saved:read(storageKey)}));
  const [notice,setNotice]=useState('');
  const activeContext=context?.contract_id===contractId?context:null;
  // 저장 후 재조회가 끝난 콜백도 현재 기준을 사용하며 다른 계약에는 쓰지 않는다.
  const latest=useRef({scope,context:activeContext});latest.current={scope,context:activeContext};
  const saved=state.scope===scope?state.saved:null;
  const draft=useMemo(()=>restore(saved,activeContext),[saved,activeContext]);
  useEffect(()=>{setState({scope,saved:read(storageKey)});setNotice('');},[scope,storageKey]);
  useEffect(()=>{
    if(!activeContext||state.scope!==scope||!saved)return;
    if(!matches(saved,activeContext)){
      setState({scope,saved:null});
      setNotice('자료가 바뀌어 이전 요청 초안을 비웠어요. 요청할 항목을 다시 확인해 주세요.');
    } else if(draft.size!==saved.items.length) {
      setState({scope,saved:{...saved,items:saved.items.filter(item=>draft.has(item.key))}});
    }
  },[activeContext,scope,state.scope,saved,draft]);
  useEffect(()=>{
    if(!storageKey||state.scope!==scope)return;
    try {
      if(state.saved?.items.length)sessionStorage.setItem(storageKey,JSON.stringify(state.saved));
      else sessionStorage.removeItem(storageKey);
    } catch {setNotice('이 브라우저에서 초안을 보관하지 못했어요. 계약을 나가기 전에 요청 내용을 작성해 주세요.');}
  },[scope,storageKey,state]);
  const setDraft=(update:Draft|((previous:Draft)=>Draft))=>{
    if(latest.current.scope!==scope||!latest.current.context)return;
    const currentContext=latest.current.context;
    setState(previous=>{
      const current=restore(previous.scope===scope?previous.saved:read(storageKey),currentContext);
      const next=typeof update==='function'?update(current):update;
      return {scope,saved:{version:1,revision:currentContext.revision,fingerprint:currentContext.fingerprint,
        items:[...next].map(([key,item])=>({key,reviewed:item.reviewed}))}};
    });
  };
  return {draft,setDraft,notice};
}
