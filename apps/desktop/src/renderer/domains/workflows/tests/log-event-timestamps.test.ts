import {afterEach,expect,it,vi} from 'vitest'
import {socketService} from '../events'
import {useWorkflowStore} from '../editor-store'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
afterEach(()=>{socketService.disconnect();useWorkflowStore.getState().clearLogs();vi.unstubAllGlobals()})
it.each(['memory','http'] as const)('preserves source timestamps for live and replayed single/batch logs over %s',async mode=>{
 vi.resetModules()
 const {mockRequest,configureMock,emitMockEvent}=await import('../api/mock-server')
 const server=mode==='http'?await startHttpStudioFixture(mockRequest):null
 const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mockRequest)
 const logs=[{id:'old-single',timestamp:'2020-01-02T03:04:05.000Z',level:'info',message:'历史单条日志',isSystemLog:true},{id:'old-batch',timestamp:'2020-01-02T03:04:06.000Z',level:'info',message:'历史批量日志',isSystemLog:true}]
 try{
  useWorkflowStore.getState().clearLogs();socketService.connect()
  await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  emitMockEvent('execution:log',{workflowId:'timestamp-run',log:logs[0]})
  emitMockEvent('execution:log_batch',{workflowId:'timestamp-run',logs:[logs[1]]})
  await vi.waitFor(()=>expect(useWorkflowStore.getState().logs).toHaveLength(2))
  expect(useWorkflowStore.getState().logs.map(log=>[log.message,log.timestamp])).toEqual(logs.map(log=>[log.message,log.timestamp]))
  socketService.disconnect();useWorkflowStore.getState().clearLogs();socketService.connect()
  await vi.waitFor(()=>expect(useWorkflowStore.getState().logs).toHaveLength(2))
  expect(useWorkflowStore.getState().logs.map(log=>log.timestamp)).toEqual(logs.map(log=>log.timestamp))
 }finally{socketService.disconnect();configureMock({disconnect:true});await server?.close();restore()}
})

it.each(['memory','http'] as const)('does not flush an old connection buffer into a cleared document over %s',async mode=>{
 vi.resetModules();const {mockRequest,configureMock,emitMockEvent}=await import('../api/mock-server')
 const server=mode==='http'?await startHttpStudioFixture(mockRequest):null;const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mockRequest)
 const marker=vi.fn(()=>{socketService.disconnect();useWorkflowStore.getState().clearWorkflow()})
 try{
  useWorkflowStore.getState().clearWorkflow();socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  socketService.on('buffer-switch',marker)
  emitMockEvent('execution:log',{workflowId:'old',log:{id:'old-buffer',timestamp:'2020-01-02T03:04:05Z',level:'warning',message:'旧连接缓冲日志'}})
  emitMockEvent('buffer-switch',{})
  await vi.waitFor(()=>expect(marker).toHaveBeenCalledOnce());await new Promise(resolve=>setTimeout(resolve,120))
  expect(useWorkflowStore.getState().logs).toEqual([])
 }finally{socketService.off('buffer-switch',marker);socketService.disconnect();configureMock({disconnect:true});await server?.close();restore()}
})


it.each(['memory','http'] as const)('deduplicates single/batch and reconnect replay while retaining distinct IDs over %s',async mode=>{
 vi.resetModules();const {mockRequest,configureMock,emitMockEvent}=await import('../api/mock-server')
 const server=mode==='http'?await startHttpStudioFixture(mockRequest):null;const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mockRequest)
 const row={id:'identity-a',timestamp:'2020-01-02T03:04:05Z',level:'warning',nodeId:'same-node',message:'重复轮次内容',details:{value:42}}
 try{
  useWorkflowStore.getState().clearWorkflow();socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  emitMockEvent('execution:log',{workflowId:'identity-run',log:row})
  emitMockEvent('execution:log_batch',{workflowId:'identity-run',logs:[row,{...row,id:'identity-b'}]})
  await vi.waitFor(()=>expect(useWorkflowStore.getState().logs.map(log=>log.id)).toEqual(['identity-a','identity-b']))
  expect(useWorkflowStore.getState().logs[0].details).toEqual({value:42})
  socketService.disconnect();socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  await new Promise(resolve=>setTimeout(resolve,160))
  expect(useWorkflowStore.getState().logs.map(log=>log.id)).toEqual(['identity-a','identity-b'])
 }finally{socketService.disconnect();configureMock({disconnect:true});await server?.close();restore()}
})
