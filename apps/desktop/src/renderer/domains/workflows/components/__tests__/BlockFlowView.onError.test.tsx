import { cleanup, createEvent, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Edge } from '@xyflow/react'
import { BlockFlowView } from '../BlockFlowView'
import { createBlock, generateGraphFromBlocks, parseGraphToBlocks } from '../blockFlowModel'
import { useWorkflowStore as store } from '../../editor-store'

const err = (source: string, target: string): Edge => ({ id: `${source}-err-${target}`, source, target, sourceHandle: 'error' })
const rowOf = (id: string) => document.querySelector(`[data-block-id="${id}"]`) as HTMLElement

function load() {
  const source = createBlock('print_log' as never)
  const handler = createBlock('print_log' as never)
  const g = generateGraphFromBlocks([source, handler])
  store.getState().loadWorkflow({ name: '出错分支', nodes: g.nodes, edges: [err(source.id, handler.id)] })
  return { source, handler }
}

beforeEach(() => store.getState().clearWorkflow())
afterEach(() => cleanup())

describe('模块条视图：出错时分支', () => {
  it('在来源节点下方渲染出错时标注、处理步骤和不回主流程的提示', () => {
    const { source, handler } = load()
    render(<BlockFlowView />)
    const region = screen.getByTestId(`on-error-${source.id}`)
    expect(within(region).getByText('出错时')).toBeTruthy()
    expect(within(region).getByText(/不会回到主流程/)).toBeTruthy()
    expect(region.contains(rowOf(handler.id))).toBe(true)
  })

  it('没有出错分支时不渲染该区域，可经行内按钮添加第一个处理步骤', () => {
    const step = createBlock('print_log' as never)
    store.getState().loadWorkflow({ name: '无', ...generateGraphFromBlocks([step]) })
    render(<BlockFlowView />)
    expect(screen.queryByTestId(`on-error-${step.id}`)).toBeNull()
    fireEvent.click(within(rowOf(step.id)).getByTitle('添加出错时的处理步骤'))
    fireEvent.click(screen.getByRole('button', { name: '打印日志' }))
    const [b] = parseGraphToBlocks(store.getState().nodes, store.getState().edges)
    expect(b.onError).toHaveLength(1)
    expect(store.getState().edges.some((e) => e.sourceHandle === 'error' && e.source === step.id)).toBe(true)
  })

  it('空槽放置：拖入新模块进入出错分支，图往返一致', () => {
    const { source } = load()
    render(<BlockFlowView />)
    const slot = within(screen.getByTestId(`on-error-${source.id}`)).getByText('添加「出错时」处理步骤')
    const ev = createEvent.drop(slot, { dataTransfer: { getData: (k: string) => (k === 'application/reactflow' ? 'print_log' : ''), types: ['application/reactflow'] } })
    fireEvent(slot, ev)
    const [b] = parseGraphToBlocks(store.getState().nodes, store.getState().edges)
    expect(b.onError).toHaveLength(2)
  })

  it('拖动已有块到出错分支：移入后往返仍在出错分支里', () => {
    const src = createBlock('print_log' as never)
    const other = createBlock('print_log' as never)
    const handler = createBlock('print_log' as never)
    const g = generateGraphFromBlocks([src, other, handler])
    store.getState().loadWorkflow({ name: '移动', nodes: g.nodes, edges: [{ id: 'm', source: src.id, target: other.id }, err(src.id, handler.id)] })
    render(<BlockFlowView />)
    const slot = within(screen.getByTestId(`on-error-${src.id}`)).getByText('添加「出错时」处理步骤')
    fireEvent(slot, createEvent.drop(slot, { dataTransfer: { getData: (k: string) => (k === 'application/blockmove' ? other.id : ''), types: ['application/blockmove'] } }))
    const [b] = parseGraphToBlocks(store.getState().nodes, store.getState().edges)
    expect(b.onError?.map((x) => x.id)).toEqual([handler.id, other.id])
  })

  it('删除出错分支里的步骤后分支消失', () => {
    const { source, handler } = load()
    render(<BlockFlowView />)
    fireEvent.click(within(rowOf(handler.id)).getByTitle('删除'))
    expect(screen.queryByTestId(`on-error-${source.id}`)).toBeNull()
  })

  it('没有起始节点时顶部显示提示条，有起始节点时不显示', () => {
    const a = createBlock('print_log' as never)
    const b = createBlock('print_log' as never)
    const g = generateGraphFromBlocks([a, b])
    store.getState().loadWorkflow({ name: '环', nodes: g.nodes, edges: [{ id: '1', source: a.id, target: b.id }, { id: '2', source: b.id, target: a.id }] })
    render(<BlockFlowView />)
    expect(screen.getByRole('alert').textContent).toContain('没有可以开始的节点')
    cleanup()
    store.getState().loadWorkflow({ name: '好', ...g })
    render(<BlockFlowView />)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
