import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest'
import {recorderApi,browserApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'

describe.each(['memory','http'] as const)('recording review service %s',mode=>{
 let service:typeof import('../api/mock-server'),restore:()=>void,fixture:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 beforeEach(async()=>{
  const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value),removeItem:(key:string)=>storage.delete(key)})
  vi.resetModules();service=await import('../api/mock-server')
  fixture=mode==='http'?await startHttpStudioFixture(service.mockRequest):undefined
  restore=configureStudioConnection(fixture?.origin??'http://autoflow-studio.mock',fixture?fetch:service.mockRequest)
 })
 afterEach(async()=>{await browserApi.close();await fixture?.close();restore();vi.unstubAllGlobals()})
 it('persists reviewed steps by document with revision conflicts and complete large values',async()=>{
  const documentId=crypto.randomUUID(),value='汉'.repeat(70000)
  const events=[{sequence:2,type:'input' as const,selector:'#name',value,variableName:'recorded'},{sequence:1,type:'navigate' as const,url:'https://local.test',navigation:'open'}]
  expect((await recorderApi.readReview(documentId)).httpStatus).toBe(404)
  const saved=await recorderApi.saveReview(documentId,{expectedRevision:0,autoWait:false,events})
  expect(saved).toMatchObject({success:true,data:{documentId,revision:1,events,autoWait:false}})
  expect((await recorderApi.saveReview(documentId,{expectedRevision:0,autoWait:true,events:[]})).httpStatus).toBe(409)
  expect(await recorderApi.readReview(documentId)).toMatchObject({success:true,data:{revision:1,events}})
  expect((await recorderApi.readReview('another-document')).httpStatus).toBe(404)
 })
 it('reads recordings in bounded pages and assembles all confirmed stop-tail pages',async()=>{
  await browserApi.open();await recorderApi.start('paged-review')
  for(let i=0;i<451;i++)service.addMockRecordingEvent({type:'click',selector:`#${i}`})
  expect(await recorderApi.events('paged-review')).toMatchObject({success:true,data:{nextSeq:200,hasMore:true}})
  const stopped=await recorderApi.stop('paged-review')
  expect(stopped.success).toBe(true);expect(stopped.data?.data.events).toHaveLength(451)
  expect(stopped.data?.nextSeq).toBe(451);expect(stopped.data?.hasMore).toBe(false)
  const retry=await recorderApi.stop('paged-review');expect(retry.data).toEqual(stopped.data)
 })
 it('preserves confirmed review after module restart of the persistent fixture',async()=>{
  const documentId=crypto.randomUUID();const saved=await recorderApi.saveReview(documentId,{expectedRevision:0,autoWait:true,events:[]});expect(saved.success).toBe(true)
  // Restart only the fixture's in-memory module, keeping this test's storage.
  const old=service;vi.resetModules();service=await import('../api/mock-server')
  const response=await service.mockRequest(`http://autoflow-studio.mock/api/recorder/reviews/${documentId}`)
  expect(await response.json()).toMatchObject({documentId,revision:1,events:[]})
  old.configureMock({disconnect:true})
 })
})
