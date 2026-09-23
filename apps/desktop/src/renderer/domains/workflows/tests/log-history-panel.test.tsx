import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { LogPanel } from '../components/LogPanel'
import { useWorkflowStore } from '../editor-store'
import { seedMockRunHistory } from '../api/mock-server'
import { workflowApi } from '../api'

beforeEach(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  })
  vi.stubGlobal('ResizeObserver', class { observe() {}; unobserve() {}; disconnect() {} })
  Element.prototype.scrollIntoView = vi.fn()
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.setState({
    bottomPanelTab: 'logs', maxLogCount: 100,
    currentExecutionWorkflowId: 'workflow-history', currentExecutionRunId: 'run-history',
    nodes: [
      { id: 'node-a', type: 'module', position: { x: 0, y: 0 }, data: { moduleType: 'open_page', label: '打开页面' } },
      { id: 'node-b', type: 'module', position: { x: 0, y: 100 }, data: { moduleType: 'click_element', label: '点击元素' } },
    ],
  })
  seedMockRunHistory({
    runId: 'run-history', workflowId: 'workflow-history', documentId: useWorkflowStore.getState().id,
    logs: Array.from({ length: 650 }, (_, index) => ({
      id: `history-${index + 1}`, timestamp: new Date(Date.UTC(2026, 8, 14, 0, 0, index)).toISOString(),
      level: index === 600 ? 'error' as const : 'info' as const,
      nodeId: index % 2 ? 'node-b' : 'node-a',
      message: index === 600 ? '故障-00601' : `调度-${String(index + 1).padStart(5, '0')}`,
    })),
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
it('hides the previous run immediately while the new run response is pending or rejected',async()=>{
 render(<LogPanel/>);await screen.findByText('100/650')
 fireEvent.change(screen.getByPlaceholderText('搜索日志...'),{target:{value:'故障-00601'}})
 await screen.findByText('1/1')
 expect(screen.getByText('故障-00601')).toBeTruthy()
 let finish!:(result:Awaited<ReturnType<typeof workflowApi.getRunLogs>>)=>void
 vi.spyOn(workflowApi,'getRunLogs').mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
 act(()=>useWorkflowStore.setState({currentExecutionRunId:'run-new',logs:[{id:'stale',timestamp:new Date().toISOString(),level:'error',message:'旧Store日志也不能冒充新运行'}]}))
 expect(screen.queryByText('故障-00601')).toBeNull()
 expect(screen.queryByText('旧Store日志也不能冒充新运行')).toBeNull()
 expect(screen.queryByRole('button',{name:'更早日志'})).toBeNull()
 await waitFor(()=>expect(finish).toBeDefined())
 await act(async()=>finish({success:false,error:'当前运行读取失败'}))
 expect(screen.queryByText('故障-00601')).toBeNull()
 expect(screen.queryByText('旧Store日志也不能冒充新运行')).toBeNull()
 expect(screen.getByText(/完整日志读取失败：当前运行读取失败/)).toBeTruthy()
})

it('queries the complete run on the service and prepends older pages', async () => {
  render(<LogPanel />)
  await screen.findByText('100/650')
  fireEvent.click(screen.getByRole('button', { name: '更早日志' }))
  await screen.findByText('200/650')
})

it('applies keyword, level and node filters to the service query', async () => {
  const query = vi.spyOn(workflowApi, 'getRunLogs')
  render(<LogPanel />)
  await screen.findByText('100/650')
  fireEvent.change(screen.getByPlaceholderText('搜索日志...'), { target: { value: '故障-00601' } })
  await screen.findByText('1/1')
  expect(screen.getByText('故障-00601')).toBeDefined()
  fireEvent.click(screen.getByRole('combobox', { name: '按节点筛选日志' }))
  fireEvent.click(await screen.findByRole('option', { name: '点击元素' }))
  await waitFor(() => expect(query).toHaveBeenLastCalledWith('run-history', expect.objectContaining({ query: '故障-00601', nodeId: 'node-b' })))
})

it('downloads the server export instead of the retained UI window', async () => {
  const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:history')
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  render(<LogPanel />)
  await screen.findByText('100/650')
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '下载' })) })
  await waitFor(() => expect(createUrl).toHaveBeenCalled())
  expect((createUrl.mock.calls[0][0] as Blob).size).toBeGreaterThan(20_000)
  expect(click).toHaveBeenCalledOnce()
})

it('restores the latest persisted run when the live execution identity is absent', async () => {
  useWorkflowStore.setState({ currentExecutionWorkflowId: null, currentExecutionRunId: null, logs: [] })
  expect((await workflowApi.listRuns()).data?.items.map(item => item.runId)).toContain('run-history')
  const list = vi.spyOn(workflowApi, 'listRuns')
  render(<LogPanel />)
  const run = await screen.findByRole('combobox', { name: '运行日志记录' })
  await waitFor(() => expect(list).toHaveBeenCalled())
  await waitFor(() => expect(run.textContent).toContain('Mock 运行'))
  fireEvent.click(run)
  fireEvent.click(await screen.findByRole('option', { name: /Mock 运行/ }))
  await screen.findByText('100/650')
})

it('refreshes the persisted run summary after a lifecycle event',async()=>{
  const list=vi.spyOn(workflowApi,'listRuns')
    .mockResolvedValueOnce({success:true,data:{items:[{runId:'run-history',workflowId:'workflow-history',documentId:useWorkflowStore.getState().id,workflowName:'状态刷新',status:'running',startedAt:'2026-09-14T00:00:00Z',finishedAt:null,logCount:650}],total:1,nextCursor:null}})
    .mockResolvedValue({success:true,data:{items:[{runId:'run-history',workflowId:'workflow-history',documentId:useWorkflowStore.getState().id,workflowName:'状态刷新',status:'completed',startedAt:'2026-09-14T00:00:00Z',finishedAt:'2026-09-14T00:00:01Z',logCount:650}],total:1,nextCursor:null}})
  render(<LogPanel/>);await waitFor(()=>expect(screen.getByRole('combobox',{name:'运行日志记录'}).textContent).toContain('running'))
  window.dispatchEvent(new CustomEvent('studio:run-history-changed',{detail:{runId:'run-history',status:'completed'}}))
  await waitFor(()=>expect(screen.getByRole('combobox',{name:'运行日志记录'}).textContent).toContain('completed'))
  expect(list).toHaveBeenCalledTimes(2)
})

it('loads older run pages and retains the explicitly selected older run after refresh',async()=>{
 const rows=Array.from({length:1000},(_,index)=>({runId:`paged-${index}`,workflowId:'flow',documentId:'doc',workflowName:`分页运行${index}`,status:'completed' as const,startedAt:new Date().toISOString(),finishedAt:null,logCount:0}))
 const list=vi.spyOn(workflowApi,'listRuns').mockImplementation(async(_doc,cursor=0,limit=50)=>({success:true,data:{items:rows.slice(cursor,cursor+limit),total:1000,nextCursor:cursor+limit<1000?cursor+limit:null}}))
 vi.spyOn(workflowApi,'getRunLogs').mockImplementation(async runId=>({success:true,data:{runId,workflowId:'flow',items:[],total:0,nextCursor:null}}))
 render(<LogPanel/>);fireEvent.click(await screen.findByText('更早运行'))
 await waitFor(()=>expect(list).toHaveBeenLastCalledWith(undefined,50,50))
 fireEvent.click(screen.getByRole('combobox',{name:'运行日志记录'}))
 fireEvent.click(await screen.findByRole('option',{name:/分页运行99 /}))
 act(()=>window.dispatchEvent(new Event('studio:run-history-changed')))
 await waitFor(()=>expect(list).toHaveBeenLastCalledWith(undefined,0,50))
 expect(screen.getByRole('combobox',{name:'运行日志记录'}).textContent).toContain('分页运行99')
})


it('shows local command feedback beside persisted history without presenting it as run evidence', async () => {
  render(<LogPanel />)
  await screen.findByText('100/650')
  act(() => useWorkflowStore.getState().addLog({ level: 'error', message: '执行失败: 缺少项目能力' }))
  expect(screen.getByRole('alert').textContent).toContain('执行失败: 缺少项目能力')
  expect(screen.getByText('100/650')).toBeTruthy()
  act(() => useWorkflowStore.getState().addLogBatch([{ level: 'info', message: '运行事件不覆盖操作提示' }]))
  expect(screen.getByRole('alert').textContent).toContain('执行失败: 缺少项目能力')
  act(() => useWorkflowStore.getState().addLog({ origin: 'run', level: 'success', message: '执行完成' }))
  expect(screen.getByRole('alert').textContent).toContain('执行失败: 缺少项目能力')
  act(() => useWorkflowStore.getState().addLog({ level: 'success', message: '工作流已保存: 项目文档' }))
  expect(screen.queryByRole('alert')).toBeNull()
  expect(screen.getByRole('status').textContent).toContain('工作流已保存: 项目文档')
  expect(screen.getByText('100/650')).toBeTruthy()
  act(() => useWorkflowStore.getState().clearLogs())
  expect(screen.queryByText(/工作流已保存: 项目文档/)).toBeNull()
})
