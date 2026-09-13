import {expect,it,vi} from 'vitest'
import {socketService} from '../events'
import {useWorkflowStore} from '../editor-store'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('retains the originating workflow identity in healing suggestions over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 const listener=vi.fn();window.addEventListener('selector:healed',listener)
 try{
  useWorkflowStore.getState().clearWorkflow();socketService.bindExecutionDocument('origin-document', 'editor-document');socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  const heals=[{nodeId:'node',configKey:'selector',oldSelector:'#old',newSelector:'#new'}]
  mock.emitMockEvent('execution:completed',{workflowId:'origin-document',result:{status:'completed',executedNodes:1,failedNodes:0},healedSelectors:heals})
  await vi.waitFor(()=>expect(listener).toHaveBeenCalledTimes(1))
  expect((listener.mock.calls[0][0] as CustomEvent).detail).toEqual({workflowId:'origin-document',documentId:'editor-document',heals})
 }finally{window.removeEventListener('selector:healed',listener);socketService.disconnect();mock.configureMock({disconnect:true});await server?.close();restore();useWorkflowStore.getState().clearWorkflow()}
})
