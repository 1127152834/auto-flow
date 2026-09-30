import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {browserApi,recorderApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'

describe.each(['memory','http'] as const)('recorder ownership over %s',mode=>{
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|null
 let restore:()=>void
 let raw:(path:string,body?:unknown)=>Promise<Response>
 beforeEach(async()=>{
  vi.resetModules();mock=await import('../api/mock-server')
  server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
  restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
  raw=(path,body)=>{const init=body===undefined?{}:{method:'POST',body:JSON.stringify(body)};return server?fetch(`${server.origin}/api${path}`,init):mock.mockRequest(`http://autoflow-studio.mock/api${path}`,init)}
 })
 afterEach(async()=>{await browserApi.close();await server?.close();restore()})
 it('reports empty, active and stopped states with the same session and confirmed tail',async()=>{
  expect(await recorderApi.status()).toMatchObject({success:true,data:{sessionId:null,recording:false,paused:false,nextSeq:0}})
  await browserApi.open();await recorderApi.start('record')
  mock.addMockRecordingEvent({type:'input',selector:'#name',value:'中文'})
  expect(await recorderApi.status('record')).toMatchObject({success:true,data:{sessionId:'record',recording:true,nextSeq:1}})
  expect(await recorderApi.start('record')).toMatchObject({success:true,data:{nextSeq:1}})
  expect(await recorderApi.stop('record')).toMatchObject({success:true,data:{data:{events:[{sequence:1,value:'中文'}]}}})
  expect(await recorderApi.status('record')).toMatchObject({success:true,data:{recording:false,nextSeq:1}})
  expect(await recorderApi.start('record')).toMatchObject({success:false})
 })
 it('requires an explicit identity for reads and writes and rejects another session',async()=>{
  await browserApi.open();await recorderApi.start('record')
  for(const path of ['/recorder/start','/recorder/stop'])expect((await raw(path,{})).status).toBe(422)
  expect((await raw('/recorder/events')).status).toBe(422)
  for(const path of ['/recorder/events?sessionId=other','/recorder/status?sessionId=other'])expect((await raw(path)).status).toBe(409)
  expect((await raw('/recorder/stop',{sessionId:'other',commandId:'stop-other'})).status).toBe(409)
  expect(mock.mockSnapshot().recording).toBe(true)
 })
 it('does not let an old stopped session stop a newer recording',async()=>{
  await browserApi.open();await recorderApi.start('first');await recorderApi.stop('first');await recorderApi.start('second')
  expect(await recorderApi.stop('first')).toMatchObject({success:false,httpStatus:409})
  expect(await recorderApi.events('first')).toMatchObject({success:false,httpStatus:409})
  expect(await recorderApi.status('second')).toMatchObject({success:true,data:{recording:true}})
 })
})

it('pauses and resumes the same recording without capturing paused operations',async()=>{
 vi.resetModules();const mock=await import('../api/mock-server');const restore=configureStudioConnection('http://autoflow-studio.mock',mock.mockRequest)
 try{
  await browserApi.open();await recorderApi.start('pause-recording')
  mock.addMockRecordingEvent({type:'input',selector:'#name',value:'暂停前'})
  expect(await recorderApi.pause('pause-recording')).toMatchObject({success:true,data:{recording:true,paused:true,data:{events:[{value:'暂停前'}]}}})
  expect(()=>mock.addMockRecordingEvent({type:'click',selector:'#ignored'})).toThrow('录制已暂停')
  expect(await recorderApi.status('pause-recording')).toMatchObject({success:true,data:{paused:true}})
  expect(await recorderApi.resume('pause-recording',1)).toMatchObject({success:true,data:{recording:true,paused:false}})
  mock.addMockRecordingEvent({type:'click',selector:'#captured'})
  expect(await recorderApi.stop('pause-recording',1)).toMatchObject({success:true,data:{data:{events:[{selector:'#captured'}]}}})
 }finally{await browserApi.close();restore()}
})

it.each(['start','stop'] as const)('recovers a lost recorder %s HTTP response without replaying the command',async action=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 const paths:string[]=[]
 const server=await startHttpStudioFixture(async(input,init)=>{paths.push(new URL(input instanceof Request?input.url:String(input)).pathname);return mock.mockRequest(input,init)})
 const restore=configureStudioConnection(server.origin,fetch)
 try{
  await browserApi.open()
  if(action==='stop'){await recorderApi.start('record');mock.addMockRecordingEvent({type:'input',selector:'#name',value:'确认尾部'})}
  paths.length=0;server.dropNextResponse(`/api/recorder/${action}`)
  const result=await recorderApi[action]('record')
  expect(result.success).toBe(true)
  expect(paths.filter(path=>path===`/api/recorder/${action}`)).toHaveLength(1)
  expect(paths.some(path=>path.startsWith('/api/recorder/commands/'))).toBe(true)
  if(action==='stop')expect(result).toMatchObject({data:{nextSeq:1,data:{events:[{value:'确认尾部'}]}}})
 }finally{await browserApi.close();await server.close();restore()}
})

it.each(['pause','resume'] as const)('recovers a lost recorder %s HTTP response without replaying the command',async action=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 const paths:string[]=[]
 const server=await startHttpStudioFixture(async(input,init)=>{paths.push(new URL(input instanceof Request?input.url:String(input)).pathname);return mock.mockRequest(input,init)})
 const restore=configureStudioConnection(server.origin,fetch)
 try{
  await browserApi.open();await recorderApi.start('record')
  if(action==='resume')await recorderApi.pause('record')
  paths.length=0;server.dropNextResponse(`/api/recorder/${action}`)
  const result=await recorderApi[action]('record')
  expect(result).toMatchObject({success:true,data:{recording:true,paused:action==='pause'}})
  expect(paths.filter(path=>path===`/api/recorder/${action}`)).toHaveLength(1)
  expect(paths.some(path=>path.startsWith('/api/recorder/commands/'))).toBe(true)
 }finally{await browserApi.close();await server.close();restore()}
})

it.each([
 {success:true,sessionId:null,recording:true,nextSeq:0},
 {success:true,sessionId:'',recording:false,nextSeq:0},
 {success:true,sessionId:'record',recording:'false',nextSeq:0},
 {success:true,sessionId:'record',recording:false,nextSeq:-1},
 {success:true,sessionId:'record',recording:false,nextSeq:0.5},
 {success:true,sessionId:'record',recording:false,nextSeq:'1'},
 {success:true,sessionId:'record',recording:true,paused:'false',nextSeq:1},
 {success:true,sessionId:'record',recording:false,paused:true,nextSeq:1},
])('rejects malformed recorder status %j',async value=>{
 const restore=configureStudioConnection('http://recorder-invalid.test',async()=>Response.json(value))
 try{expect(await recorderApi.status()).toMatchObject({success:false,error:'录制状态身份或结构错误'})}finally{restore()}
})

it('reports a definite rejection when recovery confirms that the lost startup was never accepted',async()=>{
 const restore=configureStudioConnection('http://recorder-unaccepted.test',async input=>{
  if(String(input).endsWith('/start'))throw new TypeError('Failed to fetch')
  return Response.json({success:false,error:'会话不存在'}, {status:409})
 })
 try{
  const result=await recorderApi.start('never-accepted')
  expect(result).toMatchObject({success:false,httpStatus:409})
  expect(result.outcomeUnknown).not.toBe(true)
 }finally{restore()}
})

import {beforeEach as beforeBrowserNode} from 'vitest'
import {selectBrowserNode} from './select-browser-node'
beforeBrowserNode(()=>selectBrowserNode())
