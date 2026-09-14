import {expect,it,vi} from 'vitest'
import {workflowApi} from '../api'
import {stopStudioRun} from '../lib/stopStudioRun'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('does not stop a replacement run of the same workflow over %s',async mode=>{
 const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value)})
 vi.resetModules();const mock=await import('../api/mock-server');const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  const flow=(await workflowApi.create({name:'停止身份',nodes:[{id:'node',type:'open_page',data:{moduleType:'open_page',url:'http://local.test'}}],edges:[],variables:[]})).data!
  expect((await workflowApi.execute(flow.id,{runId:'first',documentId:'doc',stepMode:true})).success).toBe(true)
  expect((await stopStudioRun(flow.id,'first'))?.status).toBe('stopped')
  expect((await workflowApi.execute(flow.id,{runId:'second',documentId:'doc',stepMode:true})).success).toBe(true)
  expect((await stopStudioRun(flow.id,'first'))?.runId).toBe('first')
  await vi.waitFor(async()=>expect((await workflowApi.getRun('second')).data?.status).toBe('paused'))
  expect(await stopStudioRun('wrong-workflow','second')).toBeNull()
  expect((await stopStudioRun(flow.id,'second'))?.status).toBe('stopped')
 }finally{const active=mock.mockSnapshot().run;if(active)await workflowApi.stop(active);mock.configureMock({disconnect:true});await server?.close();restore();vi.unstubAllGlobals()}
})
it('rejects a terminal response belonging to another run',async()=>{
 const restore=configureStudioConnection('http://stop-test.local',async()=>Response.json({runId:'other',workflowId:'wf',status:'stopped'}))
 try{expect(await stopStudioRun('wf','expected')).toBeNull()}finally{restore()}
})
