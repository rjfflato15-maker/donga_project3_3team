import {useCallback,useEffect,useRef,useState} from 'react';
import {requestJson} from '../api/client';
import {ReviewContext} from '../components/review/reviewFields';

export function useContractReviewContext(contractId:number,revision:number,updatedAt:string,evidenceDocumentId?:number) {
  const [context,setContext]=useState<ReviewContext|null>(null),[error,setError]=useState('');
  const sequence=useRef(0),active=useRef<AbortController|null>(null);
  const refresh=useCallback(async()=>{
    const token=++sequence.current,controller=new AbortController();active.current?.abort();active.current=controller;
    const query=evidenceDocumentId==null?'include_evidence=false':`evidence_document_id=${evidenceDocumentId}`;
    try{const value=await requestJson<ReviewContext>(`/api/contracts/${contractId}/review-context?${query}`,{signal:controller.signal});
      if(controller.signal.aborted||token!==sequence.current)return null;
      if(!value.documents||!Number.isFinite(value.revision))throw new Error('확인 목록을 읽지 못했습니다. 다시 불러오세요.');
      setContext(value);setError('');return value;
    }catch(reason){if(!controller.signal.aborted&&token===sequence.current){setContext(null);setError(reason instanceof Error?reason.message:'확인 목록을 불러오지 못했습니다.');}return null;}
  },[contractId,evidenceDocumentId]);
  useEffect(()=>{setContext(null);setError('');void refresh();return()=>{sequence.current++;active.current?.abort();};},[refresh,revision,updatedAt]);
  return {context,error,refresh};
}
