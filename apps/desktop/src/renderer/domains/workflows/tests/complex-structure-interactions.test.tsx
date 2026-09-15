import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@xyflow/react', async (importOriginal) => {
  const original = await importOriginal<typeof import('@xyflow/react')>()
  return {
    ...original,
    Handle: () => null,
    NodeResizer: ({ onResizeEnd }: { onResizeEnd?: (event: unknown, size: { width: number; height: number }) => void }) => (
      <button type="button" title="测试调整尺寸" onClick={() => onResizeEnd?.({}, { width: 420, height: 260 })} />
    ),
  }
})

import type { Edge, Node } from '@xyflow/react'
import { GroupNode } from '../components/GroupNode'
import { NoteNode } from '../components/NoteNode'
import { SubflowHeaderNode } from '../components/SubflowHeaderNode'
import { BlockFlowView } from '../components/BlockFlowView'
import {
  createBlock,
  generateGraphFromBlocks,
  insertAfter,
  parseGraphToBlocks,
} from '../components/blockFlowModel'
import { useWorkflowStore as store, type NodeData } from '../editor-store'

const node = (id: string, type: string, data: NodeData, position = { x: 0, y: 0 }): Node<NodeData> => ({ id, type, data, position })

beforeEach(() => store.getState().clearWorkflow())
afterEach(() => cleanup())

describe('分组、便签和子流程文档交互', () => {
  it('子流程分组改名同时更新稳定 ID 和旧名称引用，并可一次撤销重做', () => {
    const group = node('group', 'groupNode', { label: '旧子流程', moduleType: 'group', isSubflow: true, subflowName: '旧子流程' })
    const stableCall = node('stable-call', 'moduleNode', { label: '稳定调用', moduleType: 'subflow', subflowGroupId: 'group', subflowName: '过期显示名' })
    const legacyCall = node('legacy-call', 'moduleNode', { label: '旧调用', moduleType: 'subflow', subflowName: '旧子流程' })
    store.getState().loadWorkflow({ name: '子流程', nodes: [group, stableCall, legacyCall], edges: [] })
    const props = { id: group.id, data: group.data, selected: true } as unknown as ComponentProps<typeof GroupNode>
    render(<GroupNode {...props} />)

    fireEvent.doubleClick(screen.getByText('旧子流程'))
    const input = screen.getByPlaceholderText('子流程名称')
    fireEvent.change(input, { target: { value: '新子流程' } })
    fireEvent.blur(input)

    expect(store.getState().nodes.map((item) => item.data.subflowName)).toEqual(['新子流程', '新子流程', '新子流程'])
    expect(store.getState().hasUnsavedChanges).toBe(true)
    store.getState().undo()
    expect(store.getState().nodes.map((item) => item.data.subflowName)).toEqual(['旧子流程', '过期显示名', '旧子流程'])
    store.getState().redo()
    expect(store.getState().nodes.map((item) => item.data.subflowName)).toEqual(['新子流程', '新子流程', '新子流程'])
    const saved = store.getState().exportWorkflow()
    store.getState().clearWorkflow()
    expect(store.getState().importWorkflow(saved)).toBe(true)
    expect(store.getState().nodes.find((item) => item.id === 'stable-call')?.data).toMatchObject({
      subflowGroupId: 'group',
      subflowName: '新子流程',
    })
  })

  it('分组尺寸和吸附设置进入文档历史', () => {
    const group = node('group', 'groupNode', { label: '分组', moduleType: 'group', adhesion: true, width: 300, height: 200 })
    store.getState().loadWorkflow({ name: '分组', nodes: [group], edges: [] })
    const props = { id: group.id, data: group.data, selected: true } as unknown as ComponentProps<typeof GroupNode>
    render(<GroupNode {...props} />)
    fireEvent.click(screen.getByTitle('测试调整尺寸'))
    expect(store.getState().nodes[0].data).toMatchObject({ width: 420, height: 260 })
    store.getState().undo()
    expect(store.getState().nodes[0].data).toMatchObject({ width: 300, height: 200 })
    fireEvent.click(screen.getByTitle(/吸附已开启/))
    expect(store.getState().nodes[0].data.adhesion).toBe(false)
    store.getState().undo()
    expect(store.getState().nodes[0].data.adhesion).toBe(true)
  })

  it('拖动启用吸附的分组会带动组内多节点，并作为一次操作撤销', () => {
    const group = node('group', 'groupNode', { label: '分组', moduleType: 'group', adhesion: true, width: 300, height: 200 })
    const insideA = node('inside-a', 'moduleNode', { label: '内部一', moduleType: 'open_page', width: 80, height: 50 }, { x: 30, y: 40 })
    const insideB = node('inside-b', 'moduleNode', { label: '内部二', moduleType: 'click_element', width: 80, height: 50 }, { x: 160, y: 90 })
    const outside = node('outside', 'moduleNode', { label: '外部', moduleType: 'print_log' }, { x: 400, y: 300 })
    store.getState().loadWorkflow({ name: '分组拖动', nodes: [group, insideA, insideB, outside], edges: [] })
    store.getState().onNodesChange([{ type: 'position', id: group.id, position: { x: 20, y: 30 }, dragging: false }])
    expect(store.getState().nodes.map((item) => item.position)).toEqual([
      { x: 20, y: 30 },
      { x: 50, y: 70 },
      { x: 180, y: 120 },
      { x: 400, y: 300 },
    ])
    store.getState().undo()
    expect(store.getState().nodes.map((item) => item.position)).toEqual([
      { x: 0, y: 0 },
      { x: 30, y: 40 },
      { x: 160, y: 90 },
      { x: 400, y: 300 },
    ])
  })

  it('便签内容、格式和尺寸均可撤销且保存数据不是组件局部状态', () => {
    const note = node('note', 'noteNode', { label: '便签', moduleType: 'note', content: '原内容', fontBold: false, width: 200, height: 120 })
    store.getState().loadWorkflow({ name: '便签', nodes: [note], edges: [] })
    const props = { id: note.id, data: note.data, selected: true } as unknown as ComponentProps<typeof NoteNode>
    render(<NoteNode {...props} />)
    fireEvent.doubleClick(screen.getByText('原内容'))
    const editor = screen.getByRole('textbox')
    fireEvent.change(editor, { target: { value: '保存后的内容' } })
    fireEvent.blur(editor)
    fireEvent.click(screen.getByTitle('加粗'))
    fireEvent.click(screen.getByTitle('测试调整尺寸'))
    expect(store.getState().nodes[0].data).toMatchObject({ content: '保存后的内容', fontBold: true, width: 420, height: 260 })
    store.getState().undo()
    expect(store.getState().nodes[0].data).toMatchObject({ content: '保存后的内容', fontBold: true, width: 200, height: 120 })
    store.getState().undo()
    expect(store.getState().nodes[0].data.fontBold).toBe(false)
    store.getState().undo()
    expect(store.getState().nodes[0].data.content).toBe('原内容')
    store.getState().redo()
    store.getState().redo()
    store.getState().redo()
    const saved = store.getState().exportWorkflow()
    store.getState().clearWorkflow()
    expect(store.getState().importWorkflow(saved)).toBe(true)
    expect(store.getState().nodes[0].data).toMatchObject({ content: '保存后的内容', fontBold: true, width: 420, height: 260 })
  })

  it('子流程头改名和折叠下游节点均写入同一文档历史', () => {
    const header = node('header', 'subflowHeaderNode', { label: '旧名称', moduleType: 'subflow_header', subflowName: '旧名称' })
    const first = node('first', 'moduleNode', { label: '第一步', moduleType: 'open_page' })
    const second = node('second', 'moduleNode', { label: '第二步', moduleType: 'click_element' })
    const call = node('call', 'moduleNode', { label: '调用', moduleType: 'subflow', subflowGroupId: 'header', subflowName: '旧显示' })
    const edges: Edge[] = [
      { id: 'header-first', source: 'header', target: 'first' },
      { id: 'first-second', source: 'first', target: 'second' },
    ]
    store.getState().loadWorkflow({ name: '子流程头', nodes: [header, first, second, call], edges })
    const props = { id: header.id, data: header.data, selected: true } as unknown as ComponentProps<typeof SubflowHeaderNode>
    const view = render(<SubflowHeaderNode {...props} />)
    fireEvent.doubleClick(screen.getByText('旧名称'))
    const input = screen.getByPlaceholderText('子流程名称')
    fireEvent.change(input, { target: { value: '新名称' } })
    fireEvent.blur(input)
    expect(store.getState().nodes.find((item) => item.id === 'header')?.data).toMatchObject({ label: '新名称', subflowName: '新名称' })
    expect(store.getState().nodes.find((item) => item.id === 'call')?.data.subflowName).toBe('新名称')
    store.getState().undo()
    expect(store.getState().nodes.find((item) => item.id === 'call')?.data.subflowName).toBe('旧显示')

    view.unmount()
    const restoredHeader = store.getState().nodes.find((item) => item.id === 'header')!
    const restoredProps = { id: restoredHeader.id, data: restoredHeader.data, selected: true } as unknown as ComponentProps<typeof SubflowHeaderNode>
    render(<SubflowHeaderNode {...restoredProps} />)
    fireEvent.click(screen.getByTitle('折叠子流程'))
    expect(store.getState().nodes.find((item) => item.id === 'header')?.data.collapsed).toBe(true)
    expect(store.getState().nodes.find((item) => item.id === 'first')?.hidden).toBe(true)
    expect(store.getState().nodes.find((item) => item.id === 'second')?.hidden).toBe(true)
    expect(store.getState().nodes.find((item) => item.id === 'call')?.hidden).not.toBe(true)
    store.getState().undo()
    expect(store.getState().nodes.find((item) => item.id === 'first')?.hidden).not.toBe(true)
  })
})

describe('模块条真实组件交互', () => {
  it('在条件分支插入步骤、重排顶层块并通过全局历史撤销', () => {
    const condition = createBlock('condition' as never)
    const tail = createBlock('print_log' as never)
    const graph = generateGraphFromBlocks(insertAfter([condition], condition.id, tail))
    store.getState().loadWorkflow({ name: '模块条', ...graph })
    render(<BlockFlowView />)

    fireEvent.click(screen.getByText('添加「是」分支步骤'))
    fireEvent.click(screen.getByRole('button', { name: '打印日志' }))
    let blocks = parseGraphToBlocks(store.getState().nodes, store.getState().edges)
    expect(blocks[0].kind).toBe('if')
    if (blocks[0].kind !== 'if') throw new Error('条件块丢失')
    expect(blocks[0].then).toHaveLength(1)

    const conditionRow = document.querySelector(`[data-block-id="${condition.id}"]`) as HTMLElement
    fireEvent.click(within(conditionRow).getByTitle('下移'))
    blocks = parseGraphToBlocks(store.getState().nodes, store.getState().edges)
    expect(blocks.map((block) => block.id)).toEqual([tail.id, condition.id])
    store.getState().undo()
    expect(parseGraphToBlocks(store.getState().nodes, store.getState().edges).map((block) => block.id)).toEqual([condition.id, tail.id])
  })

  it('删除模块后保留分组和便签且不留下悬空连线', () => {
    const step = createBlock('print_log' as never)
    const graph = generateGraphFromBlocks([step])
    const group = node('group', 'groupNode', { label: '保留分组', moduleType: 'group' })
    const note = node('note', 'noteNode', { label: '保留便签', moduleType: 'note', content: '说明' })
    store.getState().loadWorkflow({
      name: '混合视图',
      nodes: [...graph.nodes, group, note],
      edges: [...graph.edges, { id: 'group-step', source: group.id, target: step.id }],
    })
    render(<BlockFlowView />)
    const row = document.querySelector(`[data-block-id="${step.id}"]`) as HTMLElement
    fireEvent.click(within(row).getByTitle('删除'))
    expect(store.getState().nodes.map((item) => item.id).sort()).toEqual(['group', 'note'])
    const remaining = new Set(store.getState().nodes.map((item) => item.id))
    expect(store.getState().edges.every((edge) => remaining.has(edge.source) && remaining.has(edge.target))).toBe(true)
    store.getState().undo()
    expect(store.getState().nodes.some((item) => item.id === step.id)).toBe(true)
  })
})
