// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {HttpError,requestJson} from './client';
afterEach(()=>vi.unstubAllGlobals());
it('HTTP 오류 상태와 서버 메시지를 보존하여 충돌과 전송 실패를 구분한다',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'동시 지급 수정'}),{status:409})));
 await expect(requestJson('/synthetic')).rejects.toMatchObject({name:'HttpError',status:409,message:'동시 지급 수정'});
});
it('네트워크 오류를 HTTP 성공/충돌로 바꾸지 않는다',async()=>{
 const failure=new TypeError('offline');vi.stubGlobal('fetch',vi.fn().mockRejectedValue(failure));
 await expect(requestJson('/synthetic')).rejects.toBe(failure);expect(failure).not.toBeInstanceOf(HttpError);
});
