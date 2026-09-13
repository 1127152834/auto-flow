import {expect,it,vi} from 'vitest'
import {browserApi,elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('reports confirmed browser and picker flags over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server');const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null;const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:false,pickerActive:false}})
  await browserApi.open();expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:true,pickerActive:false}})
  await elementPickerApi.start();expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:true,pickerActive:true}})
  await elementPickerApi.stop();await browserApi.close();expect(await browserApi.getStatus()).toMatchObject({success:true,data:{isOpen:false,pickerActive:false}})
 }finally{mock.configureMock({disconnect:true});await server?.close();restore()}
})
it.each([{},null,[],{isOpen:true},{isOpen:'false',pickerActive:false},{isOpen:false,pickerActive:1}])('rejects invalid browser status %j',async value=>{
 const restore=configureStudioConnection('http://status-invalid.test',async()=>Response.json(value))
 try{expect(await browserApi.getStatus()).toMatchObject({success:false,error:'浏览器状态响应格式错误，保留最后确认状态'})}finally{restore()}
})
