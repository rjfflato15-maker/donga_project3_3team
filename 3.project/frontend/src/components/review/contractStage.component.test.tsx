// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ContractStageView } from './ContractStageView';
import { ContractDetail } from '../../types';
import { requestJson } from '../../api/client';
vi.mock('../../api/client', () => ({ requestJson: vi.fn() }));
vi.mock('./ApprovalPanel', () => ({ ApprovalPanel: () => <div>새 결재 화면</div> }));
vi.mock('./ActivityTimeline', () => ({ ActivityTimeline: () => <div>처리 이력</div> }));
vi.mock('./AssignmentPanel', () => ({ AssignmentPanel: () => null }));
const fixture: ContractDetail = {contract_id:1,title:'가상 계약',vendor_name:'가상 업체',business_number:'',contract_amount:110,review_status:'PASS',required_document_types:[],documents:[],summary:{required_document_count:0,submitted_document_count:0,completeness_rate:100,pass_count:0,fail_count:0,review_count:0,missing_count:0},checks:[],created_at:'2026-10-01',updated_at:'2026-10-01',workflow:{revision:1,fingerprint:'basis1',amount_basis:'TOTAL',tax_amount:10,payment_mode:'FULL',approval_status:'PENDING',reviews:[]}};
const props = {isMaskingEnabled:true,canEdit:true,representative:false,onBack:()=>{},onOpenDocument:()=>{},onUploadType:()=>{},menu:[]};
let closed = false;
beforeEach(() => {closed=false; vi.mocked(requestJson).mockImplementation(async (url, options) => {
  if (options?.method === 'PATCH') {closed=true; throw new Error('다른 사용자가 회신 기록을 변경했습니다');}
  if (url.endsWith('/resubmission-requests')) return [{request_id:1,contract_id:1,contact_method:'EMAIL',requested_on:'2026-10-01',due_on:null,memo:'통장사본 요청',status:closed?'RECEIVED':'WAITING_RESPONSE',actor_name:'가상 담당자',bundle:{request_revision:closed?2:1,counts:{total:1,waiting:closed?0:1,received:closed?1:0,cancelled:0},items:[{item_id:1,issue_key:'missing:bank_account',title:'통장사본',document_type:'bank_account',document_id:null,reason:'미제출',status:closed?'RECEIVED':'WAITING_RESPONSE',resolution_note:null}]}}];
  if (url.includes('bundle-context')) return {contract_id:1,revision:1,fingerprint:'basis1',document_counts:{required:0,received:0,missing:0},vendor_candidates:[],internal_items:[],reading_items:[],pending_items:[],legacy_pending_request_count:0};
  return {text:'가상 계약 요약'};
});});
afterEach(() => {cleanup(); vi.resetAllMocks();});
it('마지막 회신 저장 충돌 후 결재 단계와 다른 탭에서도 실패 이유가 남는다', async () => {
  function Wrapper() {const [contract,setContract]=useState({...fixture,stage:'WAITING'} as ContractDetail);return <ContractStageView {...props} contract={contract} onChanged={async()=>{setContract({...fixture,stage:'APPROVAL'} as ContractDetail);}}/>;}
  render(<Wrapper/>);
  fireEvent.click(screen.getByRole('tab',{name:/요청 내역/}));
  fireEvent.click(await screen.findByRole('checkbox',{name:'통장사본 선택'}));
  fireEvent.change(screen.getByLabelText('받은 내용 또는 취소 이유'),{target:{value:'가상 통장사본 수신'}});
  fireEvent.click(screen.getByRole('button',{name:'받은 1건 기록'}));
  expect(await screen.findByRole('alert')).toHaveProperty('textContent',expect.stringContaining('다른 사용자가 회신 기록을 변경했습니다'));
  expect(screen.queryByRole('checkbox',{name:'통장사본 선택'})).toBeNull();
  fireEvent.click(screen.getByRole('tab',{name:'결재'}));
  expect(screen.getByText('새 결재 화면')).toBeTruthy();
  expect(screen.getByRole('alert').textContent).toContain('최신 상태를 다시 불러왔어요');
});
it('지급일이 한국 오늘보다 미래이면 지급 완료 기록 버튼을 잠근다', () => {
  render(<ContractStageView {...props} contract={{...fixture,stage:'PAYMENT'} as ContractDetail} onChanged={async()=>{}}/>);
  fireEvent.change(screen.getByText('지급일').parentElement!.querySelector('input')!,{target:{value:'2999-01-01'}});
  expect((screen.getByRole('button',{name:'계약 전체 지급 완료로 기록'}) as HTMLButtonElement).disabled).toBe(true);
});
