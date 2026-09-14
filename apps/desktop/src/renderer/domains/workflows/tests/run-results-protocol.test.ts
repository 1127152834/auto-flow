import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {configureStudioConnection} from '../api/config'
import {workflowApi} from '../api'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
beforeEach(()=>{
 const data=new Map<string,string>()
 vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
})
afterEach(()=>vi.unstubAllGlobals())
it.each(['memory','http'] as const)('isolates repeated results, pages fixed snapshots and exports complete large values over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 const restore=configureStudioConnection(server?.origin||'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  for(const runId of ['result-run','other-run'])mock.seedMockRunHistory({runId,workflowId:'same-flow',documentId:'same-doc',logs:[]})
  const large='首'+ '中'.repeat(70_000)+'尾'
  const rows=Array.from({length:135},(_,index)=>({sequence:index+1,nodeId:'repeated-node',executionId:`iteration-${index+1}`,values:{number:index,nested:{ok:true},'路径/a':index===0?large:'small'},largeValues:{}}))
  mock.seedMockRunResults('result-run',rows)
  const first=await workflowApi.getRunResults('result-run')
  expect(first).toMatchObject({success:true,data:{runId:'result-run',total:135,throughSequence:135,nextCursor:100}})
  expect(first.data?.items).toHaveLength(100)
  expect(first.data?.items[0].values).not.toHaveProperty('路径/a')
  expect(first.data?.items[0].largeValues?.['路径/a']?.length).toBeLessThan(200)
  expect((await workflowApi.getRunResultValue('result-run',1,'路径/a')).data?.value).toBe(large)
  mock.seedMockRunResults('result-run',[...rows,{...rows[0],sequence:136,executionId:'later'}])
  const next=await workflowApi.getRunResults('result-run',100,100,first.data!.throughSequence)
  expect(next.data).toMatchObject({total:135,nextCursor:null,throughSequence:135})
  expect(next.data?.items).toHaveLength(35)
  const exported=await workflowApi.exportRunResults('result-run',135)
  const lines=(await exported.data!.text()).trim().split('\n').map(line=>JSON.parse(line))
  expect(lines).toHaveLength(135)
  expect(lines[0].values['路径/a']).toBe(large)
  expect(lines.at(-1)).toMatchObject({runId:'result-run',sequence:135,executionId:'iteration-135'})
  expect((await workflowApi.getRunResults('other-run')).data).toMatchObject({total:0,items:[]})
  expect((await workflowApi.getRunResults('missing')).success).toBe(false)
  expect((await workflowApi.getRunResults('result-run',-1)).success).toBe(false)
  expect((await workflowApi.getRunResultValue('other-run',1,'路径/a')).success).toBe(false)
  vi.resetModules();const recovered=await import('../api/mock-server')
  const result=await recovered.mockRequest('http://autoflow-studio.mock/api/workflow-runs/result-run/results?cursor=100&throughSequence=135')
  expect(await result.json()).toMatchObject({runId:'result-run',total:135,nextCursor:null})
 }finally{restore();await server?.close()}
})
it('rejects a result page or full value from another run',async()=>{
 const restore=configureStudioConnection('http://result-identity.test',async()=>Response.json({runId:'wrong',workflowId:'same',items:[],total:0,throughSequence:0,nextCursor:null,sequence:1,key:'value',value:'wrong'}))
 try{
  expect((await workflowApi.getRunResults('expected')).success).toBe(false)
  expect((await workflowApi.getRunResultValue('expected',1,'value')).success).toBe(false)
 }finally{restore()}
})
