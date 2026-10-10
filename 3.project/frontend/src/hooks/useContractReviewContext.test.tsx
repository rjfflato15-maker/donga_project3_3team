// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,renderHook,waitFor} from '@testing-library/react';
import {requestJson} from '../api/client';
import {useContractReviewContext} from './useContractReviewContext';
vi.mock('../api/client',()=>({requestJson:vi.fn()}));
afterEach(()=>{cleanup();vi.resetAllMocks();});

it('overview reads skip evidence; opening a document loads only its evidence',async()=>{
  vi.mocked(requestJson).mockResolvedValue({revision:1,documents:[]});
  const {rerender,result}=renderHook(({documentId}:{documentId?:number})=>useContractReviewContext(14,1,'now',documentId),{initialProps:{documentId:undefined as number|undefined}});
  await waitFor(()=>expect(result.current.context?.revision).toBe(1));
  expect(vi.mocked(requestJson).mock.calls[0][0]).toBe('/api/contracts/14/review-context?include_evidence=false');
  rerender({documentId:5});
  await waitFor(()=>expect(vi.mocked(requestJson).mock.calls.length).toBe(2));
  expect(vi.mocked(requestJson).mock.calls[1][0]).toBe('/api/contracts/14/review-context?evidence_document_id=5');
});

it('a delayed original read cannot replace the newer overview after leaving the document',async()=>{
  let resolveOld!:(value:unknown)=>void;
  vi.mocked(requestJson).mockImplementation(async url=>url.includes('evidence_document_id')?new Promise(resolve=>{resolveOld=resolve;}):{revision:2,documents:[]});
  const {rerender,result}=renderHook(({documentId}:{documentId?:number})=>useContractReviewContext(14,2,'now',documentId),{initialProps:{documentId:5 as number|undefined}});
  rerender({documentId:undefined});
  await waitFor(()=>expect(result.current.context?.revision).toBe(2));
  resolveOld({revision:1,documents:[]});
  await waitFor(()=>expect(result.current.context?.revision).toBe(2));
});
