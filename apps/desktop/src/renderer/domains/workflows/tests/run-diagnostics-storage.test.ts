import {afterEach,expect,it,vi} from 'vitest'
afterEach(()=>vi.unstubAllGlobals())
it('rejects a diagnostic write atomically when fixture persistence fails',async()=>{
 const values=new Map<string,string>();let fail=false
 vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{if(fail)throw new Error('测试存储已满');values.set(key,value)}})
 vi.resetModules();const mock=await import('../api/mock-server')
 const request=(path:string,body:unknown={},method='POST')=>mock.mockRequest('http://autoflow-studio.mock/api'+path,{method,...(method==='GET'?{}:{body:JSON.stringify(body)})})
 await request('/workflows',{id:'storage',nodes:[{id:'n',type:'open_page'}],variables:[{name:'count',value:1}]})
 await request('/workflows/storage/execute',{runId:'storage-run',stepMode:true})
 await vi.waitFor(()=>expect(mock.mockSnapshot().pause?.pauseId).toBeTruthy())
 const pause=mock.mockSnapshot().pause!
 try{
  fail=true
  expect((await request('/workflows/storage/debug/variables',{commandId:'quota',...pause,changes:[{name:'count',value:2},{name:'new_value',value:'不得部分应用'}]})).status).toBe(500)
  fail=false
  const state=await(await request('/workflows/global-variables',{},'GET')).json()
  expect(state.variables).toEqual({count:1})
  expect(mock.mockSnapshot().pause?.controlRevision).toBe(pause.controlRevision)
  expect((await(await request('/workflow-runs/storage-run/variable-tracking',{},'GET')).json()).total).toBe(1)
 }finally{fail=false;await request('/workflows/storage/stop');mock.configureMock({disconnect:true})}
})
it('does not admit a half-created run when initial diagnostics cannot be persisted',async()=>{
 const values=new Map<string,string>();let fail=false
 vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{if(fail)throw new Error('测试存储已满');values.set(key,value)}})
 vi.resetModules();const mock=await import('../api/mock-server')
 const request=(path:string,body:unknown={},method='POST')=>mock.mockRequest('http://autoflow-studio.mock/api'+path,{method,...(method==='GET'?{}:{body:JSON.stringify(body)})})
 await request('/workflows',{id:'start-storage',nodes:[{id:'n',type:'open_page'}],variables:[{name:'count',value:1}]})
 fail=true
 expect((await request('/workflows/start-storage/execute',{runId:'start-storage-run',stepMode:true})).status).toBe(500)
 fail=false
 expect(mock.mockSnapshot().run).toBeNull()
 expect((await request('/workflow-runs/start-storage-run',{},'GET')).status).toBe(404)
 expect((await request('/workflows/start-storage/execute',{runId:'start-storage-run',stepMode:true})).status).toBe(200)
 await request('/workflows/start-storage/stop');mock.configureMock({disconnect:true})
})
