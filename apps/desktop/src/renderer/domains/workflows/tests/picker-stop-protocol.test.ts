import {expect,it,vi} from 'vitest'
import {elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('does not release picking state before a confirmed stop over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server');const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null;const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  await elementPickerApi.start();
  const wrongMethod = server ? await fetch(`${server.origin}/api/element-picker/stop`) : await mock.mockRequest('http://autoflow-studio.mock/api/element-picker/stop')
  expect(wrongMethod.status).toBe(405);expect(mock.mockSnapshot().picking).toBe(true)
  mock.configureMock({failNextPickerStop:true})
  expect(await elementPickerApi.stop()).toMatchObject({success:false,error:`HTTP 503: ${mode==='http'?'Service Unavailable':''} - Mock 拾取清理失败，请重试`,httpStatus:503})
  expect(mock.mockSnapshot().picking).toBe(true)
  expect(await elementPickerApi.stop()).toMatchObject({success:true})
  expect(mock.mockSnapshot().picking).toBe(false)
 }finally{await elementPickerApi.stop();mock.configureMock({disconnect:true});await server?.close();restore()}
})
