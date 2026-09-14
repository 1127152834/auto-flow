import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {configureStudioConnection} from '../api/config'
import {variableTrackingApi} from '../api'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
beforeEach(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
afterEach(()=>vi.unstubAllGlobals())
it.each(['memory','http'] as const)('serves complete run diagnostics with bounded pages, filters and stable high water after clear: %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 const restore=configureStudioConnection(server?.origin||'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  for(const runId of ['diagnostic-run','other-run'])mock.seedMockRunHistory({runId,workflowId:'same-flow',documentId:'same-doc',logs:[]})
  const large='起'+ '中'.repeat(70_000)+'末尾可检索'
  const rows=Array.from({length:1000},(_,index)=>({sequence:index+1,executionId:`execution-${index+1}`,timestamp:new Date().toISOString(),variable_name:index%2?'output':'count',old_value:null,new_value:index===0?large:index,node_id:'repeat',node_name:'循环节点',operation:'create' as const,value_type:index===0?'string':'number',largeValues:{}}))
  mock.seedMockRunTracking('diagnostic-run',rows)
  const first=await variableTrackingApi.listRun('diagnostic-run',{limit:100})
  expect(first).toMatchObject({success:true,data:{runId:'diagnostic-run',total:1000,throughSequence:1000,nextCursor:100}})
  expect(first.data?.tracking).toHaveLength(100)
  expect(first.data?.tracking[0]).toMatchObject({new_value:null,largeValues:{new_value:expect.any(String)}})
  expect((await variableTrackingApi.getRunValue('diagnostic-run',1,'new_value')).data?.value).toBe(large)
  const filtered=await variableTrackingApi.listRun('diagnostic-run',{query:'末尾可检索'})
  expect(filtered.data).toMatchObject({total:1,nextCursor:null})
  expect((await variableTrackingApi.listRun('diagnostic-run',{variable:'output',valueType:'number',operation:'create'})).data?.total).toBe(500)
  mock.seedMockRunTracking('diagnostic-run',[...rows,{...rows[0],sequence:1001,new_value:'later'}])
  const next=await variableTrackingApi.listRun('diagnostic-run',{cursor:900,throughSequence:1000})
  expect(next.data).toMatchObject({total:1000,nextCursor:null,throughSequence:1000})
  expect(next.data?.tracking[99].sequence).toBe(1000)
  const exported=await variableTrackingApi.exportRun('diagnostic-run',1000,{query:'末尾可检索'})
  const lines=(await exported.data!.text()).trim().split('\n').map(line=>JSON.parse(line))
  expect(lines).toHaveLength(1);expect(lines[0].new_value).toBe(large)
  expect((await variableTrackingApi.listRun('other-run')).data?.total).toBe(0)
  expect((await variableTrackingApi.getRunValue('other-run',1,'new_value')).success).toBe(false)
  vi.resetModules();const recovered=await import('../api/mock-server')
  expect(await (await recovered.mockRequest('http://autoflow-studio.mock/api/workflow-runs/diagnostic-run/variable-tracking?cursor=900&throughSequence=1000')).json()).toMatchObject({total:1000,nextCursor:null})
  expect((await variableTrackingApi.clearRun('diagnostic-run')).success).toBe(true)
  expect((await variableTrackingApi.getRunValue('diagnostic-run',1,'new_value')).success).toBe(false)
  expect((await variableTrackingApi.listRun('diagnostic-run')).data).toMatchObject({total:0,throughSequence:1001})
  mock.seedMockRunTracking('diagnostic-run',[{...rows[0],sequence:1002,new_value:'new'}])
  expect((await variableTrackingApi.listRun('diagnostic-run',{throughSequence:1001})).data?.tracking).toEqual([])
 }finally{restore();await server?.close()}
})
it('rejects wrong run responses for listing, full values and clear',async()=>{
 const restore=configureStudioConnection('http://tracking-identity.test',async()=>Response.json({runId:'other',tracking:[],total:0,nextCursor:null,throughSequence:0,sequence:1,key:'new_value',value:null,message:'清空'}))
 try{
  expect((await variableTrackingApi.listRun('expected')).success).toBe(false)
  expect((await variableTrackingApi.getRunValue('expected',1,'new_value')).success).toBe(false)
  expect((await variableTrackingApi.clearRun('expected')).success).toBe(false)
 }finally{restore()}
})
