// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {api,requestJson} from '../../api/client';
import {DocumentResponse} from '../../types';
import {DocumentComparison} from './DocumentChangeSummary';
import {DocumentWorkspace} from './DocumentWorkspace';

vi.mock('../../api/client',()=>({api:{getDocument:vi.fn(),correctFields:vi.fn()},requestJson:vi.fn(),downloadProtected:vi.fn()}));
vi.mock('../../hooks/useVlmReread',()=>({useVlmReread:()=>({result:null,busy:false,error:'',status:null,reread:vi.fn(),refresh:vi.fn()})}));
const initial:DocumentResponse={document_id:4,contract_id:1,document_type:'estimate',original_file_name:'가상.docx',file_available:true,confidence:1,processing_status:'COMPLETED',mask_status:'MASKED',analysis:{fields:{company_name:'가상 업체',business_registration_no:'000-00-00000',total_amount:3300000,supply_amount:3000000,tax_amount:300000,amount_scope:'FULL',issue_date:'2026-10-08'},warnings:[]},version:{logical_document_id:3,version_number:2,is_current:true,previous_document_id:3}};
let doc:DocumentResponse;
let comparison:DocumentComparison;
const oldFields={...initial.analysis.fields,total_amount:3600000,supply_amount:3300000};
const makeComparison=(current:DocumentResponse,previous:Record<string,unknown>):DocumentComparison=>({revision:5,previous_document_id:3,new_document_id:current.document_id,previous_version:1,new_version:2,previous_fields:previous,new_fields:current.analysis.fields as Record<string,unknown>,changes:Object.keys(previous).filter(key=>previous[key]!==current.analysis.fields[key as keyof typeof current.analysis.fields]).map(field=>({field,previous_value:previous[field],new_value:current.analysis.fields[field as keyof typeof current.analysis.fields]}))});
const respond=async(url:string)=>url.endsWith('/compare')?comparison:url.endsWith('/versions')?{versions:[{document_id:3,version_number:1,is_current:false},{document_id:doc.document_id,version_number:2,is_current:true}]}:url.includes('text-preview')?{text:'合성 문서의 원문'}:{revision:5,documents:[{document_id:doc.document_id,source_version_verified:true,fields:Object.fromEntries(Object.entries(doc.analysis.fields).map(([key,value])=>[key,{value,source:'RULE',evidence:[]}]))}]};
beforeEach(()=>{
  HTMLElement.prototype.scrollIntoView=vi.fn();
  doc=structuredClone(initial);comparison=makeComparison(doc,oldFields);
  vi.mocked(requestJson).mockImplementation(respond);
  vi.mocked(api.getDocument).mockResolvedValue({...initial,document_id:3,analysis:{fields:oldFields,warnings:[]},version:{...initial.version!,version_number:1,is_current:false,previous_document_id:null}});
});
afterEach(()=>{cleanup();vi.resetAllMocks();});
const props={checks:[],revision:5,isMaskingEnabled:true,canEdit:true,onClose:()=>{},onChanged:async()=>{}};
const summary=()=>screen.getByRole('region',{name:'수정본 변경 요약'});

it('변경을 먼저 보여 주며 항목 선택만으로 값이나 원문 확인 기록을 바꾸지 않는다',async()=>{
  comparison.changes.push({field:'amount',previous_value:3600000,new_value:3300000});
  render(<DocumentWorkspace {...props} doc={doc}/>);
  await screen.findByRole('button',{name:'합계 변경 확인'});
  const totalChange=screen.getByRole('button',{name:'합계 변경 확인'});
  expect(within(totalChange).getByText('3,600,000원')).toBeTruthy();expect(within(totalChange).getByText('3,300,000원')).toBeTruthy();
  expect(within(summary()).queryByText('금액 (기존 필드)')).toBeNull();
  fireEvent.click(within(summary()).getByText('같은 항목 5개'));
  expect(within(summary()).getByText(/사업자번호 같음/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'합계 변경 확인'}));
  expect(screen.getByRole('button',{name:'합계 상세 보기'}).getAttribute('aria-pressed')).toBe('true');
  expect(api.correctFields).not.toHaveBeenCalled();expect(vi.mocked(requestJson).mock.calls.some(([,options])=>options?.method==='POST')).toBe(false);
});
it('사업자번호와 계좌 변경은 가림 상태에서도 변화가 드러나지만 실제 값은 노출하지 않는다',async()=>{
  doc={...doc,document_type:'bank_account',analysis:{fields:{business_registration_no:'111-22-33333',account_number:'123-456-789012',bank_name:'가상 은행'},warnings:[]}};
  comparison=makeComparison(doc,{...doc.analysis.fields,business_registration_no:'444-55-66666',account_number:'456-789-123456'});
  render(<DocumentWorkspace {...props} doc={doc}/>);await screen.findByRole('button',{name:'입금 계좌 변경 확인'});
  for(const value of ['111-22-33333','444-55-66666','123-456-789012','456-789-123456'])expect(summary().textContent).not.toContain(value);
  fireEvent.click(screen.getByRole('button',{name:'입금 계좌 변경 확인'}));
  await screen.findByText('合성 문서의 원문');
  expect(screen.getByRole('button',{name:'원문과 같음'})).toHaveProperty('disabled',true);
});
it('0원은 같은 값으로 인정하지만 양쪽의 판독 누락은 같음에 포함하지 않는다',async()=>{
  doc={...doc,analysis:{fields:{total_amount:null,supply_amount:100,tax_amount:0,company_name:null,business_registration_no:null,amount_scope:'UNKNOWN',issue_date:null},warnings:[]}};
  comparison=makeComparison(doc,{...doc.analysis.fields,total_amount:100,supply_amount:null});
  render(<DocumentWorkspace {...props} doc={doc}/>);await screen.findByRole('button',{name:'합계 변경 확인'});
  expect(within(summary()).getByText('이번 본 못 읽음')).toBeTruthy();expect(within(summary()).getByText('새로 읽음')).toBeTruthy();expect(within(summary()).getByText('양쪽 모두 못 읽음 4개')).toBeTruthy();
  fireEvent.click(within(summary()).getByText('같은 항목 1개'));expect(within(summary()).getByText('부가세 같음')).toBeTruthy();
});
it('변경이 없어도 비교 완료를 알리며 원문 확인은 자동 처리하지 않는다',async()=>{
  comparison=makeComparison(doc,doc.analysis.fields as Record<string,unknown>);
  render(<DocumentWorkspace {...props} doc={doc}/>);
  expect(await screen.findByText('읽은 값의 차이가 없어요.')).toBeTruthy();expect(screen.queryByRole('button',{name:/변경 확인$/})).toBeNull();expect(api.correctFields).not.toHaveBeenCalled();
});
it('비교가 실패하면 변경 없음을 표시하지 않고 다시 조회할 수 있다',async()=>{
  let fail=true;vi.mocked(requestJson).mockImplementation(async url=>{if(url.endsWith('/compare')&&fail)throw new Error('비교 조회 실패');return respond(url);});
  render(<DocumentWorkspace {...props} doc={doc}/>);await screen.findByText('비교 조회 실패');expect(screen.queryByText('읽은 값의 차이가 없어요.')).toBeNull();
  fail=false;fireEvent.click(screen.getByRole('button',{name:'변경 요약 다시 불러오기'}));expect(await screen.findByRole('button',{name:'합계 변경 확인'})).toBeTruthy();
});
it('오래된 자료 기준의 비교 결과를 현재 수정본에 붙이지 않는다',async()=>{
  comparison={...comparison,revision:4};render(<DocumentWorkspace {...props} doc={doc}/>);
  expect(await screen.findByText('자료가 변경되었어요. 최신 계약을 불러온 뒤 비교해 주세요.')).toBeTruthy();expect(screen.queryByRole('button',{name:'합계 변경 확인'})).toBeNull();
});
it('다른 서류로 이동한 뒤 늦게 도착한 비교 결과를 버린다',async()=>{
  let resolve!:(value:DocumentComparison)=>void;const oldComparison=comparison;
  vi.mocked(requestJson).mockImplementation(async url=>url==='/api/documents/4/compare'?new Promise(r=>{resolve=r;}):respond(url));
  const view=render(<DocumentWorkspace {...props} doc={doc}/>);await screen.findByText('바뀐 항목을 비교하고 있어요.');
  doc={...doc,document_id:5,analysis:{...doc.analysis,fields:{...doc.analysis.fields,total_amount:10000000}}};comparison=makeComparison(doc,{...oldFields,total_amount:9000000});
  view.rerender(<DocumentWorkspace {...props} doc={doc}/>);await screen.findByRole('button',{name:'합계 변경 확인'});
  await act(async()=>resolve(oldComparison));expect(within(summary()).getByText('10,000,000원')).toBeTruthy();expect(within(summary()).queryByText('3,600,000원')).toBeNull();
});
it('이전 본 보기는 같은 문서의 이전 ID로 이동하고 첫 본에는 요약이 없다',async()=>{
  const select=vi.fn();const view=render(<DocumentWorkspace {...props} doc={doc} onSelectDocument={select}/>);
  fireEvent.click(await screen.findByRole('button',{name:'1차본 원문 보기'}));await waitFor(()=>expect(select).toHaveBeenCalledWith(expect.objectContaining({document_id:3,version:expect.objectContaining({is_current:false})})));
  expect(api.getDocument).toHaveBeenCalledWith(3);
  view.rerender(<DocumentWorkspace {...props} doc={{...doc,version:{...doc.version!,version_number:1,is_current:false,previous_document_id:null}}}/>);
  expect(screen.queryByRole('region',{name:'수정본 변경 요약'})).toBeNull();
});
