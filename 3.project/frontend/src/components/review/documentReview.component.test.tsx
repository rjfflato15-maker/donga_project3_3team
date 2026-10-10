// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DocumentWorkspace } from './DocumentWorkspace';
import { DocumentResponse } from '../../types';
import { api, requestJson } from '../../api/client';
vi.mock('../../api/client',()=>({api:{correctFields:vi.fn()},requestJson:vi.fn(),downloadProtected:vi.fn()}));
const doc:DocumentResponse={document_id:4,contract_id:1,document_type:'estimate',original_file_name:'가상.docx',file_available:true,confidence:1,processing_status:'COMPLETED',mask_status:'MASKED',analysis:{fields:{company_name:'가상 거래처',tax_amount:0,total_amount:100},warnings:[]},version:{logical_document_id:4,version_number:1,is_current:true,previous_document_id:null}};
const provenance={document_id:4,fields:{company_name:{value:'가상 거래처',source:'RULE',evidence:[]},tax_amount:{value:0,source:'RULE',evidence:[]},total_amount:{value:100,source:'RULE',evidence:[]}}};
beforeEach(()=>{HTMLElement.prototype.scrollIntoView=vi.fn();vi.mocked(requestJson).mockImplementation(async(url)=>url.includes('text-preview')?{text:'가상 견적서 세액 0원 합계 100원'}:url.includes('confirm-field')?{field:'total_amount',revision:4,confirmed_at:'2026-10-07T01:00:00+00:00'}:url.includes('undo-field')?{revision:5}:url.includes('provenance')?provenance:{revision:3,documents:[provenance]});vi.mocked(api.correctFields).mockResolvedValue(doc);});
afterEach(()=>{cleanup();vi.resetAllMocks();});
describe('읽은 값의 한 번 확인·되돌리기',()=>{
  it('0원도 가림 ON에서 체크박스 없이 확인하며 다음 미확인 금액을 연다',async()=>{
    const changed=vi.fn(async()=>{});
    render(<DocumentWorkspace doc={doc} checks={[]} revision={3} isMaskingEnabled canEdit onClose={()=>{}} onChanged={changed}/>);
    fireEvent.click(await screen.findByRole('button',{name:'합계 상세 보기'}));
    await screen.findByText('가상 견적서 세액 0원 합계 100원');
    expect(screen.queryByRole('checkbox')).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'원문과 같음'}));
    await waitFor(()=>expect(changed).toHaveBeenCalledOnce());
    const call=vi.mocked(requestJson).mock.calls.find(([path])=>path.endsWith('/confirm-field'))!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({field:'total_amount',revision:3});
    expect(screen.getByRole('button',{name:'부가세 상세 보기'}).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(screen.getByRole('button',{name:'되돌리기'}));
    await waitFor(()=>expect(changed).toHaveBeenCalledTimes(2));
    const undo=vi.mocked(requestJson).mock.calls.find(([path])=>path.includes('undo-field'))!;
    expect(JSON.parse(String(undo[1]?.body))).toEqual({field:'total_amount',revision:4,confirmed_at:'2026-10-07T01:00:00+00:00'});
    expect(screen.getAllByText('100원').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button',{name:'부가세 상세 보기'}));
    fireEvent.click(screen.getByRole('button',{name:'원문과 같음'}));
    await waitFor(()=>expect(changed).toHaveBeenCalledTimes(3));
    const confirmations=vi.mocked(requestJson).mock.calls.filter(([path])=>path.endsWith('/confirm-field'));
    expect(JSON.parse(String(confirmations[confirmations.length-1][1]?.body)).field).toBe('tax_amount');
  });
  it('확인 요청 실패 시 다음 항목으로 이동하지 않는다',async()=>{
    vi.mocked(requestJson).mockImplementation(async(url)=>{if(url.endsWith('/confirm-field'))throw new Error('자료 변경');return url.includes('text-preview')?{text:'원문'}:{revision:3,documents:[provenance]};});
    render(<DocumentWorkspace doc={doc} checks={[]} revision={3} isMaskingEnabled canEdit onClose={()=>{}} onChanged={async()=>{}}/>);
    fireEvent.click(await screen.findByRole('button',{name:'합계 상세 보기'}));await waitFor(()=>expect((screen.getByRole('button',{name:'원문과 같음'}) as HTMLButtonElement).disabled).toBe(false));fireEvent.click(screen.getByRole('button',{name:'원문과 같음'}));
    await screen.findByText('자료 변경');expect(screen.getByRole('button',{name:'합계 상세 보기'}).getAttribute('aria-pressed')).toBe('true');expect(screen.queryByRole('button',{name:'되돌리기'})).toBeNull();
  });
  it('가려진 거래처만 확인·수정이 비활성이고 금액은 수정할 수 있다',async()=>{
    render(<DocumentWorkspace doc={doc} checks={[]} revision={3} isMaskingEnabled canEdit onClose={()=>{}} onChanged={async()=>{}}/>);
    fireEvent.click(await screen.findByRole('button',{name:'거래처 상세 보기'}));await screen.findByText('가상 견적서 세액 0원 합계 100원');
    expect((screen.getByRole('button',{name:'원문과 같음'}) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button',{name:'다르게 적혀 있어요 · 값 수정'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'합계 상세 보기'}));fireEvent.click(screen.getByRole('button',{name:'다르게 적혀 있어요 · 값 수정'}));
    fireEvent.change(screen.getByLabelText('합계 수정값'),{target:{value:'200'}});fireEvent.change(screen.getByLabelText('수정 사유'),{target:{value:'원문 금액 확인'}});
    fireEvent.submit(screen.getByLabelText('합계 수정값').closest('form')!);
    await waitFor(()=>expect(api.correctFields).toHaveBeenCalledWith(4,{total_amount:200},'estimate',3,'원문 금액 확인',['total_amount']));
  });
  it('누락 필드는 못 읽음으로 표시하고 실제 비교 기준과 처리 상태를 구분한다',async()=>{
    render(<DocumentWorkspace doc={doc} checks={[{field:'4',rule_id:'AMOUNT_MATCH_ESTIMATE',status:'REVIEW',message:'근거 확인 필요'}]} revision={3} isMaskingEnabled canEdit onClose={()=>{}} onChanged={async()=>{}}/>);
    await screen.findByRole('button',{name:'합계 상세 보기'});expect(screen.getAllByText('못 읽음').length).toBeGreaterThan(0);expect(screen.getByRole('columnheader',{name:'비교 기준'})).toBeTruthy();expect(screen.getByRole('columnheader',{name:'처리'})).toBeTruthy();expect(screen.getAllByText('확인 필요').length).toBeGreaterThan(0);
  });
  it('판독 실패 안내는 수정본 등록에 연결하고 이전 본에는 저장 버튼이 없다',async()=>{
    const {rerender}=render(<DocumentWorkspace doc={{...doc,processing_status:'FAILED'}} checks={[]} revision={3} isMaskingEnabled canEdit onClose={()=>{}} onChanged={async()=>{}}/>);
    fireEvent.click(screen.getByRole('button',{name:'선명한 수정본 올리기'}));expect(screen.getByLabelText('도착한 수정본 파일')).toBeTruthy();expect(screen.getByLabelText('교체 사유')).toBeTruthy();
    rerender(<DocumentWorkspace doc={{...doc,version:{...doc.version!,is_current:false}}} checks={[]} revision={3} isMaskingEnabled canEdit onClose={()=>{}} onChanged={async()=>{}}/>);
    fireEvent.click(await screen.findByRole('button',{name:'합계 상세 보기'}));expect(screen.getByText('이전 본 · 읽기 전용')).toBeTruthy();expect(screen.queryByRole('button',{name:'원문과 같음'})).toBeNull();expect(screen.queryByRole('button',{name:'다르게 적혀 있어요 · 값 수정'})).toBeNull();
  });
});
