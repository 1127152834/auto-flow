import {expect,it,vi} from 'vitest'
vi.hoisted(()=>{const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)})})
import {socketService} from '../events'
import {useWorkflowStore as store} from '../editor-store'
import {useGlobalConfigStore} from '../hooks/stores/globalConfigStore'
import {useNodeRunStore} from '../hooks/stores/nodeRunStore'
import {useDebugStore} from '../hooks/stores/debugStore'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
it.each(['memory','http'] as const)('foreign terminal and data events do not end the active workflow over %s',async mode=>{
 vi.resetModules();const mock=await import('../api/mock-server');const server=mode==='http'?await startHttpStudioFixture(mock.mockRequest):null
 const restore=configureStudioConnection(server?.origin??'http://autoflow-studio.mock',server?fetch:mock.mockRequest)
 const previousConfig=useGlobalConfigStore.getState().config
 useGlobalConfigStore.setState({config:{...previousConfig,display:{...previousConfig.display,runStatusHighlight:true}}})
 const marker=vi.fn()
 try{
  store.getState().clearWorkflow();socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
  mock.emitMockEvent('execution:started',{workflowId:'active'})
  mock.emitMockEvent('execution:node_start',{workflowId:'active',nodeId:'pending'})
  mock.emitMockEvent('execution:paused',{workflowId:'active',node_id:'pending'})
  await vi.waitFor(()=>expect(useDebugStore.getState().isPaused).toBe(true))
  mock.emitMockEvent('execution:node_start',{workflowId:'foreign',nodeId:'foreign-node'})
  mock.emitMockEvent('execution:node_complete',{workflowId:'foreign',nodeId:'pending',success:false})
  mock.emitMockEvent('execution:data_row',{workflowId:'foreign',row:{unexpected:'single'}})
  mock.emitMockEvent('execution:data_row_batch',{workflowId:'foreign',rows:[{unexpected:'batch'}]})
  mock.emitMockEvent('execution:completed',{workflowId:'foreign',result:{status:'failed',executedNodes:1,failedNodes:1},collectedData:[{unexpected:'terminal'}]})
  mock.emitMockEvent('execution:stopped',{workflowId:'foreign'})
  // The ordered marker ensures all previous SSE frames have been consumed.
  socketService.on('ownership-marker',marker);mock.emitMockEvent('ownership-marker',{})
  await vi.waitFor(()=>expect(marker).toHaveBeenCalledTimes(1))
  expect(store.getState().executionStatus).toBe('running')
  expect(store.getState().currentExecutionWorkflowId).toBe('active')
  expect(useDebugStore.getState().isPaused).toBe(true)
  expect(store.getState().collectedData).toEqual([])
  expect(useNodeRunStore.getState().statuses).toEqual({pending:'running'})
  mock.emitMockEvent('execution:data_row',{workflowId:'active',row:{value:'expected'}})
  await vi.waitFor(()=>expect(store.getState().collectedData).toEqual([{value:'expected'}]))
  mock.emitMockEvent('execution:node_complete',{workflowId:'active',nodeId:'pending',success:true})
  mock.emitMockEvent('execution:completed',{workflowId:'active',result:{status:'completed',executedNodes:1,failedNodes:0}})
  await vi.waitFor(()=>expect(store.getState().executionStatus).toBe('completed'))
  expect(useDebugStore.getState().isPaused).toBe(false)
  expect(useNodeRunStore.getState().statuses.pending).toBe('success')
 }finally{useGlobalConfigStore.setState({config:previousConfig});useNodeRunStore.getState().clear();socketService.off('ownership-marker',marker);socketService.disconnect();mock.configureMock({disconnect:true});await server?.close();restore();store.getState().clearWorkflow();useDebugStore.getState().clearPaused()}
})
