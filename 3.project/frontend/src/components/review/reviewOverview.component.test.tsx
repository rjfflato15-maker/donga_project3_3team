// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {ReviewOverviewPanel} from './ReviewOverviewPanel';
import {ContractDetail} from '../../types';
import {ReviewTask} from './reviewTasks';
const contract={workflow:{approval_status:'PENDING'}} as ContractDetail;
const props={contract,tasks:[] as ReviewTask[],ready:true,error:'',queued:0,waiting:0,onOpen:vi.fn(),onDraft:vi.fn(),onRequests:vi.fn(),onApproval:vi.fn(),onRetry:vi.fn()};
afterEach(()=>{cleanup();vi.clearAllMocks();});
it('회신만 남으면 확인을 독촉하지 않고 요청 내역으로 보낸다',()=>{
 render(<ReviewOverviewPanel {...props} waiting={1}/>);
 expect(screen.getByText('요청한 서류의 회신을 기다리고 있어요')).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'요청 내역 보기'}));expect(props.onRequests).toHaveBeenCalledOnce();
 expect(screen.queryByRole('button',{name:'확인 계속하기'})).toBeNull();
});
it('반려된 계약은 확인 완료 문구 대신 사유와 이력으로 안내한다',()=>{
 render(<ReviewOverviewPanel {...props} contract={{workflow:{approval_status:'RETURNED'}} as ContractDetail}/>);
 expect(screen.getByText('대표가 수정을 요청했어요')).toBeTruthy();expect(screen.queryByText('확인할 항목을 정리했어요')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'반려 사유·결재 이력 보기'}));expect(props.onApproval).toHaveBeenCalledOnce();
});
it('보류만 남아도 해당 항목을 직접 열 수 있다',()=>{
 const task={id:'4:total_amount',label:'합계',field:'total_amount',reason:'확인 필요',kind:'field',checks:[],expected:null,value:110,deferral:{note:'담당 확인',actor_name:'담당자',at:'now'}} as ReviewTask;
 render(<ReviewOverviewPanel {...props} tasks={[task]}/>);
 fireEvent.click(screen.getByRole('button',{name:'보류한 항목 확인'}));expect(props.onOpen).toHaveBeenCalledWith(task);
});
