// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DocumentReviewDialog } from './DocumentReviewDialog';
import { DocumentResponse } from '../../types';
import { api, requestJson } from '../../api/client';
vi.mock('../../api/client',()=>({api:{correctFields:vi.fn()},requestJson:vi.fn(),downloadProtected:vi.fn()}));
const doc:DocumentResponse={document_id:4,contract_id:1,document_type:'estimate',original_file_name:'가상.docx',file_available:true,confidence:1,processing_status:'COMPLETED',mask_status:'MASKED',analysis:{fields:{tax_amount:0,total_amount:100},warnings:[]},version:{logical_document_id:4,version_number:1,is_current:true,previous_document_id:null}};
beforeEach(()=>{HTMLElement.prototype.scrollIntoView=vi.fn();vi.mocked(requestJson).mockImplementation(async (url)=>url.includes('text-preview')?{text:'가상 견적서 세액 0원 합계 100원'}:{fields:{tax_amount:{value:0,source:'RULE',evidence:[],evidence_status:'UNAVAILABLE'},total_amount:{value:100,source:'RULE',evidence:[],evidence_status:'UNAVAILABLE'}}});vi.mocked(api.correctFields).mockResolvedValue(doc);});
afterEach(()=>{cleanup();vi.resetAllMocks();});
describe('원문 확인과 읽기 전용 이전 본',()=>{
  it('0원도 원문 확인 가능하며 고른 한 칸만 확인으로 전송한다',async()=>{
    const changed=vi.fn(async()=>{});
    render(<DocumentReviewDialog doc={doc} checks={[]} revision={3} isMaskingEnabled={false} canEdit onClose={()=>{}} onChanged={changed}/>);
    fireEvent.click(await screen.findByRole('button',{name:/^세액 규칙/}));
    await waitFor(()=>expect((screen.getByRole('button',{name:'원문과 같음'}) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button',{name:'원문과 같음'}));
    await waitFor(()=>expect(api.correctFields).toHaveBeenCalledWith(4,doc.analysis.fields,'estimate',3,'원문과 같은 세액 확인',['tax_amount']));
    expect(changed).toHaveBeenCalledOnce();
  });
  it('이전 본에는 수정·확인·재발행 저장 동작을 제공하지 않는다',async()=>{
    render(<DocumentReviewDialog doc={{...doc,version:{...doc.version!,is_current:false}}} checks={[]} revision={3} isMaskingEnabled canEdit onClose={()=>{}} onChanged={async()=>{}}/>);
    await screen.findByRole('button',{name:/^세액 규칙/});
    expect(screen.getByText('이전 본 · 1번째')).toBeTruthy();
    expect(screen.queryByRole('button',{name:'원문과 같음'})).toBeNull();
    expect(screen.queryByRole('button',{name:'읽은 값 수정'})).toBeNull();
    expect(screen.queryByRole('button',{name:'고친 본 올리기'})).toBeNull();
  });
});
