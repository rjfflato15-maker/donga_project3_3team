// @vitest-environment jsdom
import {beforeEach,expect,it} from 'vitest';
import {ContractDetail,DocumentResponse} from '../../types';
import {focusItems,readFocusCursor,writeFocusCursor} from './focusNavigation';
import {ReviewContext} from './reviewFields';
const doc={document_id:4,contract_id:1,document_type:'estimate',analysis:{fields:{total_amount:110,company_name:'synthetic',business_registration_no:'synthetic'},warnings:[]}} as unknown as DocumentResponse;
const contract={contract_id:1,workflow:{revision:3,fingerprint:'v3',submission:{gate:{fingerprint:'gate3'}}}} as unknown as ContractDetail;
const context:ReviewContext={revision:3,documents:[{document_id:4,fields:{total_amount:{value:110,source:'RULE',evidence:[],human_confirmation:{actor_name:'synthetic',at:'2026-10-10'}}}}]};
beforeEach(()=>sessionStorage.clear());
it('completed required fields stay available to revisit while optional blank fields do not fill the queue',()=>{
 const items=focusItems([doc],[],context);
 expect(items.map(i=>i.id)).toEqual(['4:total_amount','4:company_name','4:business_registration_no']);
});
it('resume stores only position metadata and restores against the current server basis',()=>{
 const items=focusItems([doc],[],context);writeFocusCursor(contract,'4:total_amount');
 expect(readFocusCursor(contract,items)?.field).toBe('total_amount');
 const raw=sessionStorage.getItem('c-pilot:review-position:1')!;
 expect(JSON.parse(raw)).toEqual({basis:'3|v3|gate3',item:'4:total_amount'});expect(raw).not.toContain('110');expect(raw).not.toContain('confirmed');
});
it('server revision, fingerprint and gate changes invalidate stale navigation without fabricating completion',()=>{
 const items=focusItems([doc],[],context);
 for(const change of [{revision:4},{fingerprint:'changed'},{submission:{gate:{fingerprint:'changed'}}}]){
  writeFocusCursor(contract,'4:total_amount');
  expect(readFocusCursor({...contract,workflow:{...contract.workflow!,...change}} as unknown as ContractDetail,items)).toBeUndefined();
 }
});
it('replacement originals and invalid cursor content cannot resume obsolete document ids',()=>{
 writeFocusCursor(contract,'4:total_amount');expect(readFocusCursor(contract,focusItems([{...doc,document_id:5}],[],context))).toBeUndefined();
 sessionStorage.setItem('c-pilot:review-position:1','broken');expect(readFocusCursor(contract,[])).toBeUndefined();
});
