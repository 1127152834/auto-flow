import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import type { Node } from '@xyflow/react'
import { connectToNewNode, failurePanDuration, resolveDragOutSource, useFailureFocus } from '../quickConnect'
import { useNodeRunStore } from '../../hooks/stores/nodeRunStore'
import { useWorkflowStore } from '../../editor-store'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('resolveDragOutSource', () => {
  const blank = { toNode: null, toHandle: null }
  it.each(['true', 'false', 'loop', 'done', 'error'])('从 source 句柄 %s 拖到空白处返回该句柄', (id) => {
    expect(resolveDragOutSource({ fromHandle: { nodeId: 'a', id, type: 'source' }, ...blank })).toEqual({ nodeId: 'a', handleId: id })
  })
  it('无句柄 id 时为 null 句柄', () => {
    expect(resolveDragOutSource({ fromHandle: { nodeId: 'a', id: undefined, type: 'source' }, ...blank })).toEqual({ nodeId: 'a', handleId: null })
  })
  it('从 target 句柄反向拖出不弹出', () => {
    expect(resolveDragOutSource({ fromHandle: { nodeId: 'a', id: null, type: 'target' }, ...blank })).toBeNull()
  })
  it('释放在节点或句柄上不弹出', () => {
    const fromHandle = { nodeId: 'a', id: 'true', type: 'source' as const }
    expect(resolveDragOutSource({ fromHandle, toNode: {}, toHandle: null })).toBeNull()
    expect(resolveDragOutSource({ fromHandle, toNode: {}, toHandle: {} })).toBeNull()
  })
  it('没有出发句柄时不弹出', () => {
    expect(resolveDragOutSource({ fromHandle: null, ...blank })).toBeNull()
  })
})

describe('connectToNewNode', () => {
  beforeEach(() => useWorkflowStore.getState().clearWorkflow())
  it('按来源句柄在 store 中新增连线', () => {
    const s = useWorkflowStore.getState()
    s.addNode('open_page', { x: 0, y: 0 })
    s.addNode('click_element', { x: 0, y: 200 })
    const [a, b] = useWorkflowStore.getState().nodes
    connectToNewNode({ nodeId: a.id, handleId: 'error' }, b.id, s.onConnect)
    expect(useWorkflowStore.getState().edges).toMatchObject([{ source: a.id, target: b.id, sourceHandle: 'error' }])
  })
})

describe('failurePanDuration', () => {
  it.each([['full', 280], ['reduce', 0], ['off', 0], [undefined, 280]])('motion=%s -> %i', (m, d) => {
    expect(failurePanDuration(m as string | undefined)).toBe(d)
  })
})

describe('useFailureFocus', () => {
  let container: HTMLDivElement
  let root: Root
  const setCenter = vi.fn()
  const inst = { current: { setCenter, getViewport: () => ({ zoom: 0.8 }) } }
  const nodes = [{ id: 'n1', position: { x: 100, y: 50 }, data: {}, width: 100, height: 40 }] as Node[]
  let onMoveStart: (e: unknown) => void
  function Harness({ status }: { status: string }) {
    onMoveStart = useFailureFocus(inst, nodes, status)
    return null
  }
  const render = (status: string) => act(() => { root.render(<Harness status={status} />) })

  beforeEach(() => {
    setCenter.mockClear()
    useNodeRunStore.setState({ statuses: {} })
    delete document.documentElement.dataset.motion
    container = document.createElement('div')
    root = createRoot(container)
  })
  afterEach(() => act(() => root.unmount()))

  it('运行中不平移；失败后平移一次并保持当前缩放', () => {
    render('running')
    act(() => useNodeRunStore.getState().setStatus('n1', 'failed'))
    expect(setCenter).not.toHaveBeenCalled()
    render('failed')
    expect(setCenter).toHaveBeenCalledWith(150, 70, { zoom: 0.8, duration: 280 })
    act(() => useNodeRunStore.getState().setStatus('n2', 'success'))
    render('failed')
    expect(setCenter).toHaveBeenCalledTimes(1)
  })

  it.each([['reduce'], ['off']])('动效 %s 时 duration=0', (m) => {
    document.documentElement.dataset.motion = m
    useNodeRunStore.setState({ statuses: { n1: 'failed' } })
    render('failed')
    expect(setCenter.mock.calls[0][2].duration).toBe(0)
  })

  it('失败后用户手动平移，不再定位同一次失败；下一次失败重新定位', () => {
    render('running')
    render('failed')
    act(() => onMoveStart({ type: 'mousedown' }))
    useNodeRunStore.setState({ statuses: { n1: 'failed' } })
    render('failed')
    expect(setCenter).not.toHaveBeenCalled()
    useNodeRunStore.setState({ statuses: { n1: 'failed' } })
    render('running')
    render('failed')
    expect(setCenter).toHaveBeenCalledTimes(1)
  })

  it('程序化移动（event 为空）不算用户操作', () => {
    render('running')
    render('failed')
    act(() => onMoveStart(null))
    useNodeRunStore.setState({ statuses: { n1: 'failed' } })
    render('failed')
    expect(setCenter).toHaveBeenCalledTimes(1)
  })
})
