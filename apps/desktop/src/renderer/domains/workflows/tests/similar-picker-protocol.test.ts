import {expect,it,vi} from 'vitest'
import {elementPickerApi} from '../api'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('exposes stable similar-element results only within a picker session over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 try{
  expect(()=>mock.selectMockSimilarElements()).toThrow('请先开启元素拾取')
  expect(await elementPickerApi.getSimilar()).toMatchObject({success:true,data:{selected:false,active:false}})
  await elementPickerApi.start();mock.selectMockSimilarElements()
  const selected={selected:true,active:true,similar:{pattern:'.item:nth-child({index})',count:4,indices:[1,2,3,4],minIndex:1,maxIndex:4,selector1:'.item:nth-child(1)',selector2:'.item:nth-child(2)'}}
  expect(await elementPickerApi.getSimilar()).toMatchObject({success:true,data:selected})
  expect(await elementPickerApi.getSimilar()).toMatchObject({success:true,data:selected})
  expect(await elementPickerApi.getSelected()).toMatchObject({success:true,data:{selected:false}})
  await elementPickerApi.stop()
  expect(await elementPickerApi.getSimilar()).toMatchObject({success:true,data:{selected:false,active:false}})
  await elementPickerApi.start()
  expect(await elementPickerApi.getSimilar()).toMatchObject({success:true,data:{selected:false,active:true}})
 }finally{await elementPickerApi.stop();mock.configureMock({disconnect:true});await server?.close();restore()}
})
it.each([
 {selected:true,active:true},
 {selected:true,active:true,similar:{pattern:'div',count:4,minIndex:1,maxIndex:4}},
 {selected:true,active:true,similar:{pattern:'div{index}',count:0,minIndex:1,maxIndex:4}},
 {selected:true,active:true,similar:{pattern:'div{index}',count:4,minIndex:5,maxIndex:4}},
 {selected:true,active:true,similar:{pattern:'div{index}',count:4,minIndex:1,maxIndex:4,indices:[1,5]}},
 {selected:false,active:'yes'},
])('rejects malformed similar results without applying %j',async result=>{
 const restore=configureStudioConnection('http://similar-invalid.test',async input=>Response.json(String(input).includes('/status')
  ?{success:true,sessionId:'picker',active:true,selected:false}
  :{success:true,sessionId:'picker',...result}))
 try{expect(await elementPickerApi.getSimilar()).toMatchObject({success:false,error:typeof result.active==='boolean'?'相似元素响应格式错误，未应用定位结果':'元素拾取会话响应身份或结构错误'})}finally{restore()}
})

import {beforeEach as beforeBrowserNode} from 'vitest'
import {selectBrowserNode} from './select-browser-node'
beforeBrowserNode(()=>selectBrowserNode())
