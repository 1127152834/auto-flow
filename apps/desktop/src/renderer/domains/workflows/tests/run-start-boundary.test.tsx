import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
import { Toolbar } from '../components/Toolbar'
import { useWorkflowStore as store } from '../editor-store'
import { useDebugStore } from '../hooks/stores/debugStore'
import { workflowApi } from '../api'
import { socketService } from '../events'
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
beforeEach(() => {
  store.getState().clearWorkflow()
  store.getState().addNode('open_page', { x: 0, y: 0 })
  useDebugStore.setState({ breakpoints: new Set(), stepMode: false })
  vi.spyOn(workflowApi, 'create').mockResolvedValue({ success: true, data: { id: 'start-fixture' } })
  vi.spyOn(workflowApi, 'execute').mockResolvedValue({ success: true })
  vi.spyOn(workflowApi, 'update').mockResolvedValue({ success: true })
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it.each(['completed', 'stopped', 'failed', 'pending'] as const)('does not replace confirmed %s state when the start HTTP response arrives', async status => {
  const response = deferred<Awaited<ReturnType<typeof workflowApi.execute>>>()
  vi.mocked(workflowApi.execute).mockReturnValue(response.promise)
  render(<Toolbar />)
  fireEvent.keyDown(window, { key: 'F5' })
  await waitFor(() => expect(workflowApi.execute).toHaveBeenCalledTimes(1))
  act(() => store.getState().setExecutionStatus(status))
  await act(async () => response.resolve({ success: true }))
  expect(store.getState().executionStatus).toBe(status)
})
it('coalesces repeated starts during preparation and freezes debug options before awaiting', async () => {
  const response = deferred<Awaited<ReturnType<typeof workflowApi.create>>>()
  vi.mocked(workflowApi.create).mockReturnValue(response.promise)
  const nodeId = store.getState().nodes[0].id
  useDebugStore.setState({ breakpoints: new Set([nodeId]), stepMode: true })
  render(<Toolbar />)
  fireEvent.keyDown(window, { key: 'F5' })
  fireEvent.keyDown(window, { key: 'F5' })
  expect(workflowApi.create).toHaveBeenCalledTimes(1)
  act(() => useDebugStore.setState({ breakpoints: new Set(), stepMode: false }))
  await act(async () => response.resolve({ success: true, data: { id: 'start-fixture' } }))
  expect(workflowApi.execute).toHaveBeenCalledTimes(1)
  expect(workflowApi.execute).toHaveBeenCalledWith('start-fixture', expect.objectContaining({ breakpoints: [nodeId], stepMode: true }))
})
it('releases preparation ownership after failure so an explicit retry can start', async () => {
  vi.mocked(workflowApi.create).mockResolvedValueOnce({ success: false, error: '准备失败' })
  render(<Toolbar />)
  fireEvent.keyDown(window, { key: 'F5' })
  await waitFor(() => expect(store.getState().logs.some(log => log.message.includes('准备失败'))).toBe(true))
  expect(workflowApi.execute).not.toHaveBeenCalled()
  fireEvent.keyDown(window, { key: 'F5' })
  await waitFor(() => expect(workflowApi.execute).toHaveBeenCalledTimes(1))
  expect(workflowApi.create).toHaveBeenCalledTimes(2)
})
it('does not start another request through run-from-node while a run is active', async () => {
  store.getState().setExecutionStatus('running')
  render(<Toolbar />)
  await act(async () => window.dispatchEvent(new CustomEvent('run-from-node', { detail: { nodeId: store.getState().nodes[0].id } })))
  expect(workflowApi.create).not.toHaveBeenCalled()
  expect(workflowApi.execute).not.toHaveBeenCalled()
  expect(store.getState().executionStatus).toBe('running')
})

it('binds a server workflow to the original editor document before starting', async () => {
  const original = store.getState().id
  const bind = vi.spyOn(socketService, 'bindExecutionDocument')
  const response = deferred<Awaited<ReturnType<typeof workflowApi.create>>>()
  vi.mocked(workflowApi.create).mockReturnValue(response.promise)
  render(<Toolbar />); fireEvent.keyDown(window, {key: 'F5'})
  await waitFor(() => expect(workflowApi.create).toHaveBeenCalledTimes(1))
  act(() => store.getState().clearWorkflow())
  await act(async () => response.resolve({success: true, data: {id: 'server-identity'}}))
  await waitFor(() => expect(workflowApi.execute).toHaveBeenCalledTimes(1))
  expect(bind).toHaveBeenCalledWith('server-identity', original, expect.any(String))
  const boundRunId = bind.mock.calls[0][2]
  expect(workflowApi.execute).toHaveBeenCalledWith('server-identity', expect.objectContaining({ runId: boundRunId, documentId: original }))
  expect(bind.mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(workflowApi.execute).mock.invocationCallOrder[0])
})

it('does not submit again after HTTP acceptance while the start event is still missing',async()=>{
 render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
 await waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('启动请求已接受'))).toBe(true))
 fireEvent.keyDown(window,{key:'F5'})
 await act(async()=>window.dispatchEvent(new CustomEvent('run-from-node',{detail:{nodeId:store.getState().nodes[0].id}})))
 expect(workflowApi.execute).toHaveBeenCalledTimes(1)
})
it('keeps ambiguous startup occupied instead of executing a new run after response loss',async()=>{
 vi.mocked(workflowApi.execute).mockResolvedValue({success:false,error:'网络连接中断'})
 render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
 await waitFor(()=>expect(workflowApi.execute).toHaveBeenCalledTimes(1))
 await act(async()=>{});fireEvent.keyDown(window,{key:'F5'})
 expect(workflowApi.execute).toHaveBeenCalledTimes(1)
})
it('releases an explicitly rejected startup for a deliberate retry',async()=>{
 vi.mocked(workflowApi.execute).mockResolvedValueOnce({success:false,error:'参数无效',httpStatus:422})
 vi.spyOn(workflowApi,'update').mockResolvedValue({success:true})
 render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
 await waitFor(()=>expect(store.getState().logs.some(log=>log.message.includes('参数无效'))).toBe(true))
 fireEvent.keyDown(window,{key:'F5'});await waitFor(()=>expect(workflowApi.execute).toHaveBeenCalledTimes(2))
})

it.each(['execution:started','execution:completed','execution:stopped'])('waits for its own %s confirmation and cleans listeners on unmount',async event=>{
 const listeners=new Map<string,Array<(data:{workflowId:string})=>void>>()
 vi.spyOn(socketService,'on').mockImplementation((name,callback)=>{listeners.set(name,[...(listeners.get(name)||[]),callback])})
 const off=vi.spyOn(socketService,'off')
 const view=render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
 await waitFor(()=>expect(view.getByRole('status').textContent).toContain('等待启动确认'))
 act(()=>listeners.get(event)?.forEach(callback=>callback({workflowId:'foreign'})))
 expect(view.getByRole('status').textContent).toContain('等待启动确认')
 act(()=>listeners.get(event)?.forEach(callback=>callback({workflowId:'start-fixture'})))
 expect(view.queryByText('等待启动确认')).toBeNull()
 view.unmount()
 for(const name of ['execution:started','execution:completed','execution:stopped'])expect(off).toHaveBeenCalledWith(name,listeners.get(name)?.[0])
})
it('does not restore an awaiting indicator when a terminal event precedes the HTTP receipt',async()=>{
 const response=deferred<Awaited<ReturnType<typeof workflowApi.execute>>>()
 vi.mocked(workflowApi.execute).mockReturnValue(response.promise)
 let completed:((data:{workflowId:string})=>void)|undefined
 vi.spyOn(socketService,'on').mockImplementation((name,callback)=>{if(name==='execution:completed')completed=callback})
 const view=render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
 await waitFor(()=>expect(workflowApi.execute).toHaveBeenCalledTimes(1))
 act(()=>{store.getState().setExecutionStatus('completed');completed?.({workflowId:'start-fixture'})})
 await act(async()=>response.resolve({success:true}))
 expect(store.getState().executionStatus).toBe('completed');expect(view.queryByText('等待启动确认')).toBeNull()
})
it('can stop an accepted startup without sending another execution request',async()=>{
 const stop=vi.spyOn(workflowApi,'stop').mockResolvedValue({success:true})
 const signal=vi.spyOn(socketService,'stopExecution').mockImplementation(()=>{})
 const view=render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
 await waitFor(()=>expect(view.getByRole('status').textContent).toContain('等待启动确认'))
 fireEvent.click(view.getByRole('button',{name:'停止启动请求'}))
 await waitFor(()=>expect(stop).toHaveBeenCalledWith('start-fixture'))
 expect(signal).toHaveBeenCalledWith('start-fixture');expect(workflowApi.execute).toHaveBeenCalledTimes(1)
 expect(view.getByRole('status').textContent).toContain('等待启动确认')
})
it('does not reuse a prepared server identifier for a different editor document',async()=>{
 const preparation=deferred<Awaited<ReturnType<typeof workflowApi.create>>>()
 vi.mocked(workflowApi.create).mockReturnValueOnce(preparation.promise)
 let completed:((data:{workflowId:string})=>void)|undefined
 vi.spyOn(socketService,'on').mockImplementation((name,callback)=>{if(name==='execution:completed')completed=callback})
 render(<Toolbar/>);fireEvent.keyDown(window,{key:'F5'})
 await waitFor(()=>expect(workflowApi.create).toHaveBeenCalledTimes(1))
 act(()=>{store.getState().clearWorkflow();store.getState().addNode('open_page',{x:0,y:0})})
 await act(async()=>preparation.resolve({success:true,data:{id:'old-server-id'}}))
 await waitFor(()=>expect(workflowApi.execute).toHaveBeenCalledTimes(1))
 act(()=>completed?.({workflowId:'old-server-id'}))
 fireEvent.keyDown(window,{key:'F5'});await act(async()=>{})
 expect(workflowApi.create).toHaveBeenCalledTimes(2);expect(workflowApi.update).not.toHaveBeenCalled()
})
