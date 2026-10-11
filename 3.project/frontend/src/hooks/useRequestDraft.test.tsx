// @vitest-environment jsdom
import {act,cleanup,renderHook} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {useRequestDraft} from './useRequestDraft';
import {BundleContext} from '../features/requests/model';

const context:BundleContext={contract_id:1,revision:3,fingerprint:'basis3',document_counts:{required:2,received:0,missing:2},vendor_candidates:[
  {issue_key:'missing:estimate',title:'견적서',document_type:'estimate',document_id:null,reason:'미제출',requires_original_review:false,snapshot:{privateValue:'보관하면 안 되는 값'}},
  {issue_key:'missing:bank_account',title:'통장사본',document_type:'bank_account',document_id:null,reason:'미제출',requires_original_review:false}
],internal_items:[],reading_items:[],pending_items:[],legacy_pending_request_count:0};
const props={userId:1 as number|undefined,cid:1,context:context as BundleContext|null};
const mount=()=>renderHook(p=>useRequestDraft(p.userId,p.cid,p.context),{initialProps:props});
beforeEach(()=>sessionStorage.clear());
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('같은 탭에서 다시 열면 선택을 복원하며 문서 값은 저장하지 않는다',()=>{
  const first=mount();
  act(()=>first.result.current.setDraft(old=>new Map(old).set('missing:estimate',{snapshot:'unused',reviewed:false})));
  const saved=sessionStorage.getItem('c-pilot:request-draft:v1:1:1')!;
  expect(saved).toContain('missing:estimate');expect(saved).not.toContain('보관하면 안 되는 값');expect(saved).not.toContain('snapshot');
  first.unmount();const second=mount();
  expect(second.result.current.draft.size).toBe(1);
  expect(second.result.current.draft.get('missing:estimate')?.snapshot).toContain('보관하면 안 되는 값');
});
it('계약과 사용자별로 분리하며 다른 계약에서 돌아오면 초안을 유지한다',()=>{
  const view=mount();act(()=>view.result.current.setDraft(new Map([['missing:estimate',{snapshot:'',reviewed:false}]])));
  view.rerender({...props,cid:2,context:{...context,contract_id:2}});expect(view.result.current.draft.size).toBe(0);
  view.rerender({...props,userId:2});expect(view.result.current.draft.size).toBe(0);
  view.rerender(props);expect(view.result.current.draft.size).toBe(1);
});
it('자료 기준이 바뀌면 이전 선택과 동의를 비우고 이유를 알린다',()=>{
  const view=mount();act(()=>view.result.current.setDraft(new Map([['missing:estimate',{snapshot:'',reviewed:true}]])));
  view.rerender({...props,context:{...context,revision:4,fingerprint:'basis4'}});
  expect(view.result.current.draft.size).toBe(0);expect(view.result.current.notice).toContain('자료가 바뀌어');
  expect(sessionStorage.getItem('c-pilot:request-draft:v1:1:1')).toBeNull();
});
it('이미 요청한 항목을 제거하고 같은 이벤트의 여러 선택을 모두 보존한다',()=>{
  const view=mount();act(()=>{
    view.result.current.setDraft(old=>new Map(old).set('missing:estimate',{snapshot:'',reviewed:false}));
    view.result.current.setDraft(old=>new Map(old).set('missing:bank_account',{snapshot:'',reviewed:false}));
  });expect(view.result.current.draft.size).toBe(2);
  view.rerender({...props,context:{...context,vendor_candidates:context.vendor_candidates.map(item=>({...item,already_requested:item.issue_key==='missing:estimate'}))}});
  expect([...view.result.current.draft.keys()]).toEqual(['missing:bank_account']);
});
it('사용자 식별자가 없으면 메모리에서만 유지하고 계약을 섞지 않는다',()=>{
  const view=renderHook(p=>useRequestDraft(p.userId,p.cid,p.context),{initialProps:{...props,userId:undefined}});
  act(()=>view.result.current.setDraft(new Map([['missing:estimate',{snapshot:'',reviewed:false}]])));
  expect(view.result.current.draft.size).toBe(1);expect(sessionStorage.length).toBe(0);
  view.rerender({...props,userId:undefined,cid:2,context:{...context,contract_id:2}});expect(view.result.current.draft.size).toBe(0);
});
it('브라우저 보관 실패를 알리면서 현재 선택은 사용할 수 있다',()=>{
  vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('storage denied');});
  const view=mount();act(()=>view.result.current.setDraft(new Map([['missing:estimate',{snapshot:'',reviewed:false}]])));
  expect(view.result.current.draft.size).toBe(1);expect(view.result.current.notice).toContain('보관하지 못했어요');
});
it('원문 확인 후 이어진 담기는 재조회한 최신 기준으로 저장한다',()=>{
  const view=mount(),queueAfterSave=view.result.current.setDraft;
  view.rerender({...props,context:{...context,revision:4,fingerprint:'basis4'}});
  act(()=>queueAfterSave(old=>new Map(old).set('missing:estimate',{snapshot:'',reviewed:true})));
  expect(view.result.current.draft.size).toBe(1);
  expect(JSON.parse(sessionStorage.getItem('c-pilot:request-draft:v1:1:1')!)).toMatchObject({revision:4,fingerprint:'basis4'});
});
it('다른 계약으로 이동한 뒤 끝난 이전 저장은 현재 초안을 바꾸지 않는다',()=>{
  const view=mount(),oldQueue=view.result.current.setDraft;
  view.rerender({...props,cid:2,context:{...context,contract_id:2}});
  act(()=>view.result.current.setDraft(new Map([['missing:bank_account',{snapshot:'',reviewed:false}]])));
  act(()=>oldQueue(new Map([['missing:estimate',{snapshot:'',reviewed:true}]])));
  expect([...view.result.current.draft.keys()]).toEqual(['missing:bank_account']);
});
