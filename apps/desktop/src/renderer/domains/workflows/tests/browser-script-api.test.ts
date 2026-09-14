import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {browserScriptTestsApi as api} from '../api/browserScriptTests'
import {configureStudioConnection} from '../api/config'
const target={browserSessionId:'browser',pageId:'page',revision:0}
const state={requestId:'test',context:target,status:'completed',hasResult:true,result:null,error:null,executionKind:'browser'}
let restore:()=>void
let response:unknown
let calls:number
beforeEach(()=>{calls=0;response=state;restore=configureStudioConnection('http://fixture.invalid',async()=>{calls++;return Response.json(response)})})
afterEach(()=>{restore();vi.restoreAllMocks()})
it.each([
 ['wrong id',{requestId:'other'}],['wrong page',{context:{...target,pageId:''}}],['revision',{context:{...target,revision:-1}}],
 ['state',{status:'unknown'}],['no error',{status:'failed',hasResult:false}],['partial',{status:'running'}],['no flag',{executionKind:null}],['wrong flag',{executionKind:'native'}],['result contradiction',{hasResult:false,result:1}],['success error',{error:'wrong'}],
] as const)('rejects malformed state: %s',async(_name,patch)=>{
 response={...state,...patch};const result=await api.get('test');expect(result.success).toBe(false);expect(result.error).toContain('状态格式错误')
})
it.each([['empty page',{pageId:''}],['fraction',{revision:0.5}],['no URL',{url:null}],['missing active',{activeRequestId:undefined}],['empty active',{activeRequestId:''}]] as const)('rejects malformed context: %s',async(_name,patch)=>{
 response={...target,url:'about:blank',activeRequestId:null,...patch};expect((await api.getContext()).success).toBe(false)
})
it('preserves null return value separately from no return value',async()=>{
 expect((await api.get('test')).data).toMatchObject({hasResult:true,result:null})
 response={...state,hasResult:false};expect((await api.get('test')).data).toMatchObject({hasResult:false,result:null})
})
it.each([['infinite',{x:Infinity}],['undefined',{x:undefined}],['function',{x:()=>1}]] as const)('rejects non-JSON inputs before any request: %s',(_name,variables)=>{
 expect(()=>api.start({requestId:'test',context:target,code:'return 1',variables})).toThrow('非 JSON');expect(calls).toBe(0)
})
it('rejects oversized UTF8 before posting source',()=>{
 expect(()=>api.start({requestId:'test',context:target,code:'中'.repeat(400000),variables:{}})).toThrow('1MiB');expect(calls).toBe(0)
})
