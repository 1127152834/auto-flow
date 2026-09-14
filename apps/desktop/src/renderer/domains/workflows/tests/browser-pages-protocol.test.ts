import {expect,it,vi} from 'vitest'
import {browserApi,elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('binds page select, focus and navigation to session/revision over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server');const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  expect((await browserApi.pages()).httpStatus).toBe(409)
  const profiles=await browserApi.profiles();expect(profiles.data?.items.length).toBe(1)
  expect((await browserApi.open(undefined,undefined,'missing')).httpStatus).toBe(404)
  await browserApi.open(undefined,undefined,profiles.data!.items[0].id);const initial=(await browserApi.pages()).data!
  mock.configureMockBrowserPages([{pageId:'first',url:'http://local.test/a',title:'一'},{pageId:'second',url:'http://local.test/b',title:'二'}],'first')
  const current=(await browserApi.pages()).data!
  expect((await browserApi.page({sessionId:initial.sessionId,expectedRevision:initial.revision,pageId:'second',action:'select',url:null})).httpStatus).toBe(409)
  await elementPickerApi.start();mock.selectMockElement('#old-target')
  const selected=(await browserApi.page({sessionId:current.sessionId,expectedRevision:current.revision,pageId:'second',action:'select',url:null})).data!
  expect(selected.targetPageId).toBe('second')
  expect(await elementPickerApi.getSelected()).toMatchObject({success:true,data:{active:false,selected:false}})
  const focused=(await browserApi.page({sessionId:selected.sessionId,expectedRevision:selected.revision,pageId:'second',action:'focus',url:null})).data!
  expect(focused).toEqual(selected)
  const navigated=(await browserApi.page({sessionId:selected.sessionId,expectedRevision:selected.revision,pageId:'second',action:'navigate',url:'http://local.test/new'})).data!
  expect(navigated.pages.find(page=>page.pageId==='second')?.url).toBe('http://local.test/new')
  mock.configureMockBrowserPages([navigated.pages[0]])
  expect((await browserApi.pages()).data?.targetPageId).toBeNull()
  expect((await browserApi.page({sessionId:navigated.sessionId,expectedRevision:navigated.revision,pageId:'second',action:'focus',url:null})).httpStatus).toBe(409)
  await browserApi.close();await browserApi.open()
  expect((await browserApi.pages()).data?.sessionId).not.toBe(current.sessionId)
 }finally{await browserApi.close();mock.configureMock({disconnect:true});await server?.close();restore()}
})
it.each([{sessionId:'s',revision:0,targetPageId:'missing',pages:[]},{sessionId:'s',revision:0,targetPageId:null,pages:[{pageId:'p',title:'',url:''},{pageId:'p',title:'',url:''}]}])('rejects ambiguous page identity %j',async body=>{
 const restore=configureStudioConnection('http://bad-pages.test',async()=>Response.json(body))
 try{expect((await browserApi.pages()).success).toBe(false)}finally{restore()}
})
