// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {BundleRequestPage,BundleCandidate} from './BundleRequest';
import {ContractDetail} from '../../types';
import {requestJson} from '../../api/client';
vi.mock('../../api/client',()=>({requestJson:vi.fn()}));
const items:BundleCandidate[]=[{issue_key:'missing:bank_account',title:'통장사본',document_type:'bank_account',document_id:null,reason:'미제출',requires_original_review:false},{issue_key:'document:7',title:'견적서',document_type:'estimate',document_id:7,reason:'금액 불일치',requires_original_review:true}];
const basis={contractId:1,revision:3,fingerprint:'basis3'};
const props={contract:{contract_id:1,title:'가상 계약',vendor_name:'가상 업체'} as ContractDetail,basis,latest:basis,items,reviewed:new Set(['document:7']),isMaskingEnabled:true,onClose:()=>{},onRecorded:vi.fn(async()=>{}),onStale:async()=>{}};
beforeEach(()=>{vi.mocked(requestJson).mockResolvedValue({request_id:9,bundle:{counts:{total:1}}});});
afterEach(()=>{cleanup();vi.resetAllMocks();});
it('본문에서 제외한 항목은 문구와 저장 대상에서 빠지고 원문 동의는 선택한 서류에만 전송한다',async()=>{render(<BundleRequestPage {...props}/>);expect(screen.queryByRole('dialog')).toBeNull();fireEvent.click(screen.getByRole('checkbox',{name:'통장사본 요청 선택'}));expect((screen.getByLabelText('보낼 문구') as HTMLTextAreaElement).value).not.toContain('통장사본');fireEvent.click(screen.getByRole('button',{name:'요청했어요 · 1건 기록'}));await waitFor(()=>expect(requestJson).toHaveBeenCalledOnce());const call=vi.mocked(requestJson).mock.calls[0];expect(JSON.parse(call[1]!.body as string).items).toEqual([{issue_key:'document:7',reviewed_original:true}]);expect(props.onRecorded).toHaveBeenCalledWith(expect.objectContaining({request_id:9}));});
it('작성 중 자료가 바뀌면 이전 원문 동의로 기록할 수 없다',()=>{const view=render(<BundleRequestPage {...props}/>);view.rerender(<BundleRequestPage {...props} latest={{...basis,revision:4,fingerprint:'basis4'}}/>);expect((screen.getByRole('button',{name:'요청했어요 · 2건 기록'}) as HTMLButtonElement).disabled).toBe(true);expect(screen.getByRole('alert').textContent).toContain('자료가 바뀌었습니다');expect(requestJson).not.toHaveBeenCalled();});
