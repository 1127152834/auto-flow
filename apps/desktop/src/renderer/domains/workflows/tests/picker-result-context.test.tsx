import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { elementPickerApi, systemApi } from '../api'
let nodeId: string
beforeEach(() => {
  vi.useFakeTimers()
  store.getState().clearWorkflow(); store.getState().addNode('click_element', { x: 0, y: 0 }); nodeId = store.getState().nodes[0].id
  store.getState().updateNodeData(nodeId, { selector: '#before' }); store.getState().markAsSaved()
  vi.spyOn(elementPickerApi, 'start').mockResolvedValue({ success: true, data: { success: true } })
  vi.spyOn(elementPickerApi, 'stop').mockResolvedValue({ success: true, data: { success: true } })
  vi.spyOn(elementPickerApi, 'getSimilar').mockResolvedValue({ success: true, data: { selected: false } })
  vi.spyOn(systemApi, 'setClipboard').mockResolvedValue({ success: true })
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })
async function start() {
  fireEvent.click(screen.getByTitle('可视化选择元素'))
  await act(async () => fireEvent.click(screen.getByText('启动选择器')))
}
const selected = { success: true, data: { selected: true, element: { selector: '#picked', tagName: 'BUTTON', text: '选中', attributes: { id: 'picked' } } } }
it.each(['node', 'document', 'unmount'])('does not start polling after a late startup response following %s change', async change => {
  let release!: (value: Awaited<ReturnType<typeof elementPickerApi.start>>) => void
  vi.mocked(elementPickerApi.start).mockImplementation(() => new Promise(resolve => { release = resolve }))
  const poll = vi.spyOn(elementPickerApi, 'getSelected').mockResolvedValue(selected)
  const view = render(<ConfigPanel selectedNodeId={nodeId} />); await start()
  if (change === 'node') { act(() => store.getState().addNode('click_element', { x: 10, y: 0 })); view.rerender(<ConfigPanel selectedNodeId={store.getState().nodes[1].id} />) }
  if (change === 'document') { const nodes=store.getState().nodes; act(() => {store.getState().clearWorkflow();store.setState({nodes})}) }
  if (change === 'unmount') view.unmount()
  await act(async () => release({ success: true, data: {success: true} }))
  await act(async () => vi.advanceTimersByTimeAsync(1000))
  expect(poll).not.toHaveBeenCalled()
  expect(store.getState().nodes.find(node => node.id===nodeId)?.data.selector).toBe('#before')
})
it.each(['field', 'node', 'document', 'delete', 'cancel', 'unmount'])('ignores an in-flight selected result after %s change', async change => {
  let release!: (value: Awaited<ReturnType<typeof elementPickerApi.getSelected>>) => void
  vi.spyOn(elementPickerApi, 'getSelected').mockImplementation(() => new Promise(resolve => { release=resolve }))
  const view=render(<ConfigPanel selectedNodeId={nodeId} />); await start()
  await act(async () => vi.advanceTimersByTimeAsync(500))
  if (change==='field') fireEvent.change(screen.getByDisplayValue('#before'), { target: {value:'#edited'} })
  if (change==='node') { act(() => store.getState().addNode('click_element',{x:10,y:0})); view.rerender(<ConfigPanel selectedNodeId={store.getState().nodes[1].id} />) }
  if (change==='document') { const nodes=store.getState().nodes; act(() => {store.getState().clearWorkflow();store.setState({nodes})}) }
  if (change==='delete') act(() => store.getState().deleteNode(nodeId))
  if (change==='cancel') await act(async () => fireEvent.click(screen.getByTitle('停止选择')))
  if (change==='unmount') view.unmount()
  await act(async () => release(selected))
  expect(store.getState().nodes.every(node => node.data.selector !== '#picked')).toBe(true)
  expect(systemApi.setClipboard).not.toHaveBeenCalled()
  expect(store.getState().logs.some(log => log.message==='已选择元素: #picked')).toBe(false)
})
it('never overlaps selection polls while a response is pending', async () => {
  vi.spyOn(elementPickerApi, 'getSelected').mockImplementation(() => new Promise(() => {}))
  render(<ConfigPanel selectedNodeId={nodeId} />); await start()
  await act(async () => vi.advanceTimersByTimeAsync(2000))
  expect(elementPickerApi.getSelected).toHaveBeenCalledTimes(1)
})
it('applies selector and hints as one undoable edit', async () => {
  vi.spyOn(elementPickerApi, 'getSelected').mockResolvedValue(selected)
  render(<ConfigPanel selectedNodeId={nodeId} />); await start()
  await act(async () => vi.advanceTimersByTimeAsync(500))
  expect(store.getState().nodes[0].data).toMatchObject({selector:'#picked',selectorHints:{tag:'BUTTON'}})
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data.selector).toBe('#before')
  expect(store.getState().nodes[0].data.selectorHints).toBeUndefined()
})
it.each(['field', 'node', 'document'])('ignores a late similar-elements preview after %s change', async change => {
  vi.spyOn(elementPickerApi, 'getSelected').mockResolvedValue({ success:true,data:{selected:false} })
  let release!: (value: Awaited<ReturnType<typeof elementPickerApi.getSimilar>>) => void
  vi.mocked(elementPickerApi.getSimilar).mockImplementation(() => new Promise(resolve => { release=resolve }))
  const view=render(<ConfigPanel selectedNodeId={nodeId} />);await start()
  await act(async () => vi.advanceTimersByTimeAsync(500))
  if (change==='field') fireEvent.change(screen.getByDisplayValue('#before'),{target:{value:'#edited'}})
  if (change==='node') {act(() => store.getState().addNode('click_element',{x:10,y:0}));view.rerender(<ConfigPanel selectedNodeId={store.getState().nodes[1].id} />)}
  if (change==='document') {const nodes=store.getState().nodes;act(() => {store.getState().clearWorkflow();store.setState({nodes})})}
  await act(async () => release({success:true,data:{selected:true,similar:{pattern:'.item-{index}',count:4,minIndex:1,maxIndex:4}}}))
  expect(screen.queryByText('相似元素选择')).toBeNull()
  expect(store.getState().variables).toHaveLength(0)
})
it('rejects a similar-elements confirmation when the origin field has changed', async () => {
  vi.spyOn(elementPickerApi, 'getSelected').mockResolvedValue({success:true,data:{selected:false}})
  vi.mocked(elementPickerApi.getSimilar).mockResolvedValue({success:true,data:{selected:true,similar:{pattern:'.item-{index}',count:4,minIndex:1,maxIndex:4}}})
  render(<ConfigPanel selectedNodeId={nodeId} />);await start()
  await act(async () => vi.advanceTimersByTimeAsync(500))
  act(() => store.getState().updateNodeData(nodeId,{selector:'#edited'}))
  await act(async () => fireEvent.click(screen.getByText('确认使用')))
  expect(store.getState().nodes[0].data.selector).toBe('#edited')
  expect(store.getState().variables).toHaveLength(0)
  expect(systemApi.setClipboard).not.toHaveBeenCalled()
})
it('reports a polling exception and allows the next poll to recover', async () => {
  vi.spyOn(elementPickerApi, 'getSelected').mockRejectedValueOnce(new Error('连接中断')).mockResolvedValue(selected)
  render(<ConfigPanel selectedNodeId={nodeId} />);await start()
  await act(async () => vi.advanceTimersByTimeAsync(500))
  expect(store.getState().logs.some(log => log.level==='error' && log.message.includes('连接中断'))).toBe(true)
  await act(async () => vi.advanceTimersByTimeAsync(500))
  expect(store.getState().nodes[0].data.selector).toBe('#picked')
})
