// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,act,waitFor} from '@testing-library/react';
import {ContractDashboard} from './ContractDashboard';
import {api} from '../api/client';
vi.mock('../api/client',()=>({api:{listContracts:vi.fn(),getContract:vi.fn(),llmStatus:vi.fn(),pilotInfo:vi.fn()},downloadProtected:vi.fn()}));
const auth = vi.hoisted(()=>({user:{user_id:1,role:'operator',deployment_mode:'pilot',display_name:'Test'},updateUser:vi.fn(),logout:vi.fn()}));
vi.mock('../context/AuthContext',()=>({useAuth:()=>auth}));
beforeEach(()=>{auth.user.deployment_mode='pilot';});
vi.mock('../hooks/useAutoRefresh',()=>({AUTO_REFRESH_INTERVAL_MS:10000,useAutoRefresh:()=>({invalidate:vi.fn(),refresh:vi.fn(),lastUpdated:null,error:''})}));
vi.mock('../components/AppShell',()=>({AppShell:({children,onTabChange,onOpenAutoBatchContract,loading}:any)=><main><button onClick={()=>onTabChange('dashboard')}>Inbox</button><button onClick={onOpenAutoBatchContract}>Register</button><button onClick={()=>onTabChange('account-settings')}>Settings</button><span data-testid="loading">{String(loading)}</span>{children}</main>}));
vi.mock('../components/review/StageDashboard',()=>({StageDashboard:({onOpen}:any)=><div><button onClick={()=>onOpen(1)}>Open A</button><button onClick={()=>onOpen(2)}>Open B</button></div>}));
vi.mock('../components/OverallDashboardView',()=>({OverallDashboardView:({onSelectContract}:any)=><button onClick={()=>onSelectContract(1)}>Demo contract</button>}));
vi.mock('../components/review/ContractReviewOverview',()=>({ContractReviewOverview:()=> <div data-testid="demo-review">Demo review</div>}));
vi.mock('../components/PilotOperations',()=>({PilotOperations:()=> <div>Pilot operations</div>}));
vi.mock('../components/review/MyAssignmentsStrip',()=>({MyAssignmentsStrip:()=>null}));
vi.mock('../components/CompareRegistration',()=>({CompareRegistration:({onClose}:any)=> <div>Registration<button onClick={onClose}>Close registration</button></div>}));
vi.mock('../components/review/ContractStageView',()=>({ContractStageView:({contract}:any)=><div data-testid="chosen">{contract.title}</div>}));
const contract=(id:number)=>({contract_id:id,title:id===1?'A':'B',documents:[],summary:{},checks:[],workflow:{revision:1},created_at:'2026-10-09T00:00:00'} as any);
afterEach(()=>{cleanup();vi.resetAllMocks();});
it('last contract selection wins when responses arrive in reverse order',async()=>{
 let a!:(v:any)=>void,b!:(v:any)=>void;
 vi.mocked(api.listContracts).mockResolvedValue([contract(1),contract(2)]);vi.mocked(api.pilotInfo).mockResolvedValue({} as any);vi.mocked(api.llmStatus).mockResolvedValue({} as any);
 vi.mocked(api.getContract).mockResolvedValueOnce(contract(1)).mockImplementation(id=>new Promise(resolve=>{if(id===1)a=resolve;else b=resolve;}));
 render(<ContractDashboard/>);await screen.findByRole('button',{name:'Open A'});
 fireEvent.click(screen.getByRole('button',{name:'Open A'}));fireEvent.click(screen.getByRole('button',{name:'Open B'}));
 await act(async()=>b(contract(2)));expect(screen.getByTestId('chosen').textContent).toBe('B');
 await act(async()=>a(contract(1)));expect(screen.getByTestId('chosen').textContent).toBe('B');
 expect(screen.getByTestId('loading').textContent).toBe('false');
});

function setupDeferred(){
 let resolve!:(value:any)=>void,reject!:(e:Error)=>void;
 vi.mocked(api.listContracts).mockResolvedValue([contract(1),contract(2)]);vi.mocked(api.pilotInfo).mockResolvedValue({} as any);vi.mocked(api.llmStatus).mockResolvedValue({} as any);
 vi.mocked(api.getContract).mockResolvedValueOnce(contract(1)).mockImplementation(()=>new Promise((r,j)=>{resolve=r;reject=j;}));
 return {resolve:(v:any)=>resolve(v),reject:(e:Error)=>reject(e)};
}
it.each(['Inbox','Register'])('navigation to %s invalidates a pending contract selection',async(destination)=>{
 const pending=setupDeferred();render(<ContractDashboard/>);await screen.findByRole('button',{name:'Open B'});
 fireEvent.click(screen.getByRole('button',{name:'Open B'}));fireEvent.click(screen.getByRole('button',{name:destination}));
 await act(async()=>pending.resolve(contract(2)));
 expect(screen.queryByTestId('chosen')).toBeNull();expect(screen.getByTestId('loading').textContent).toBe('false');
 if(destination==='Register'){expect(screen.getByText('Registration')).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Close registration'}));expect(screen.queryByTestId('chosen')).toBeNull();expect(screen.getByRole('button',{name:'Open B'})).toBeTruthy();}
 else expect(screen.getByRole('button',{name:'Open B'})).toBeTruthy();
});
it('a stale failure cannot clear the newer loading state or display an error',async()=>{
 let rejectA!:(e:Error)=>void,resolveB!:(v:any)=>void;
 vi.mocked(api.listContracts).mockResolvedValue([contract(1),contract(2)]);vi.mocked(api.pilotInfo).mockResolvedValue({} as any);vi.mocked(api.llmStatus).mockResolvedValue({} as any);
 vi.mocked(api.getContract).mockResolvedValueOnce(contract(1)).mockImplementation(id=>new Promise((r,j)=>{if(id===1)rejectA=j;else resolveB=r;}));
 render(<ContractDashboard/>);await screen.findByRole('button',{name:'Open A'});
 fireEvent.click(screen.getByRole('button',{name:'Open A'}));fireEvent.click(screen.getByRole('button',{name:'Open B'}));
 await act(async()=>rejectA(new Error('old failure')));expect(screen.queryByText('old failure')).toBeNull();expect(screen.getByTestId('loading').textContent).toBe('true');
 await act(async()=>resolveB(contract(2)));expect(screen.getByTestId('chosen').textContent).toBe('B');
});
it.each([
 [null,{payment_id:8,status:'VOIDED',correction_revision:1}],
 [{payment_id:8,status:'RECORDED',correction_revision:1},{payment_id:8,status:'RECORDED',correction_revision:2}],
])('payment-only lifecycle changes show the latest-state banner',async(current,latest)=>{
 const detail={...contract(1),stage:'PAYMENT',payment:current};
 vi.mocked(api.listContracts).mockResolvedValue([{...detail,revision:1,payment:latest}]);vi.mocked(api.getContract).mockResolvedValue(detail);vi.mocked(api.pilotInfo).mockResolvedValue({} as any);vi.mocked(api.llmStatus).mockResolvedValue({} as any);
 render(<ContractDashboard/>);await screen.findByRole('button',{name:'Open A'});fireEvent.click(screen.getByRole('button',{name:'Open A'}));
 await waitFor(()=>expect(screen.getByText(/이 계약의 자료·결재·지급 상태가 바뀌었습니다/)).toBeTruthy());
});

it('demo settings use the existing self-password form and demo detail still opens', async()=>{
 auth.user.deployment_mode='demo';
 vi.mocked(api.listContracts).mockResolvedValue([contract(1)]);vi.mocked(api.getContract).mockResolvedValue(contract(1));
 render(<ContractDashboard/>);await screen.findByRole('button',{name:'Demo contract'});
 fireEvent.click(screen.getByRole('button',{name:'Demo contract'}));
 expect(await screen.findByTestId('demo-review')).toBeTruthy();expect(screen.queryByTestId('chosen')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Settings'}));
 expect(screen.getByRole('heading',{name:'비밀번호 변경'})).toBeTruthy();
 expect(screen.getByLabelText('현재 비밀번호')).toBeTruthy();expect(screen.queryByText('인증번호 받기')).toBeNull();
 expect(api.pilotInfo).not.toHaveBeenCalled();
});
it.each([null,{}])('pilot settings select the existing password fallback or operations screen (%j)',async info=>{
 vi.mocked(api.listContracts).mockResolvedValue([]);vi.mocked(api.pilotInfo).mockResolvedValue(info as any);vi.mocked(api.llmStatus).mockResolvedValue({} as any);
 render(<ContractDashboard/>);await screen.findByRole('button',{name:'Open A'});fireEvent.click(screen.getByRole('button',{name:'Settings'}));
 if(info)expect(screen.getByText('Pilot operations')).toBeTruthy();else expect(screen.getByRole('heading',{name:'비밀번호 변경'})).toBeTruthy();
 expect(screen.queryByText('인증번호 받기')).toBeNull();
});
