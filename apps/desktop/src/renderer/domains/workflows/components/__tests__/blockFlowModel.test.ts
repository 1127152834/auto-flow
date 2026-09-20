// Source: WebRPA@5ccb900e, components/__tests__/blockFlowModel.test.ts; see SOURCE.md for license and adaptation boundaries.
import { describe, it, expect } from 'vitest'
import {
  createBlock,
  generateGraphFromBlocks,
  parseGraphToBlocks,
  insertIntoContainer,
  insertAfter,
  cloneBlock,
  moveBlockTo,
} from '../blockFlowModel'

describe('blockFlowModel', () => {
  it('creates subflow definitions with the callable header node type', () => {
    expect(createBlock('subflow_header').node.type).toBe('subflowHeaderNode')
  })

  it('createBlock 套用模块默认变量（循环自带 index）', () => {
    const loop = createBlock('loop' as never)
    expect(loop.kind).toBe('loop')
    // 默认变量名字段写入 node.data
    expect((loop.node.data as Record<string, unknown>).indexVariable).toBe('index')
  })

  it('createBlock 对条件类返回 if 结构', () => {
    const cond = createBlock('condition' as never)
    expect(cond.kind).toBe('if')
  })

  it('顺序块 图<->结构树 roundtrip 保持顺序', () => {
    const a = createBlock('print_log' as never)
    let blocks = [a]
    blocks = insertAfter(blocks, a.id, createBlock('print_log' as never))
    const { nodes, edges } = generateGraphFromBlocks(blocks)
    expect(nodes.length).toBe(2)
    const back = parseGraphToBlocks(nodes, edges)
    expect(back.length).toBe(2)
    expect(back.every((b) => b.kind === 'step')).toBe(true)
  })

  it('循环体末节点不回连到循环节点（回归）', () => {
    const loop = createBlock('loop' as never)
    let blocks = [loop]
    const body = createBlock('print_log' as never)
    blocks = insertIntoContainer(blocks, loop.id, 'body', body)
    const { edges } = generateGraphFromBlocks(blocks)
    // 不应存在 从循环体节点 指回 循环节点 的边
    const backEdge = edges.find((e) => e.source === body.id && e.target === loop.id)
    expect(backEdge).toBeUndefined()
  })

  it('嵌套条件与循环在图和模块条之间往返保持分支结构', () => {
    const condition = createBlock('condition' as never)
    const loop = createBlock('loop' as never)
    const yes = createBlock('click_element' as never)
    const body = createBlock('input_text' as never)
    let blocks = [condition]
    blocks = insertIntoContainer(blocks, condition.id, 'then', yes)
    blocks = insertIntoContainer(blocks, condition.id, 'els', loop)
    blocks = insertIntoContainer(blocks, loop.id, 'body', body)
    const graph = generateGraphFromBlocks(blocks)
    const restored = parseGraphToBlocks(graph.nodes, graph.edges)
    expect(restored).toHaveLength(1)
    expect(restored[0]).toMatchObject({ kind: 'if', id: condition.id })
    if (restored[0].kind !== 'if') throw new Error('条件结构未恢复')
    expect(restored[0].then.map((block) => block.id)).toEqual([yes.id])
    expect(restored[0].els[0]).toMatchObject({ kind: 'loop', id: loop.id })
    if (restored[0].els[0].kind !== 'loop') throw new Error('循环结构未恢复')
    expect(restored[0].els[0].body.map((block) => block.id)).toEqual([body.id])
  })

  it('复制完整控制块时重映射内部引用并保留外部定义引用', () => {
    const condition = createBlock('condition' as never)
    const first = createBlock('print_log' as never)
    const second = createBlock('click_element' as never, {
      subflowGroupId: 'external-definition',
      errorPolicy: { mode: 'retry-from', targetId: first.id },
    } as never)
    let blocks = [condition]
    blocks = insertIntoContainer(blocks, condition.id, 'then', first)
    blocks = insertAfter(blocks, first.id, second)
    const copied = cloneBlock(blocks[0])
    expect(copied.id).not.toBe(condition.id)
    if (copied.kind !== 'if') throw new Error('复制后条件结构丢失')
    const [copiedFirst, copiedSecond] = copied.then
    expect(copiedFirst.id).not.toBe(first.id)
    expect(copiedSecond.id).not.toBe(second.id)
    expect(copiedSecond.node.data.errorPolicy?.targetId).toBe(copiedFirst.id)
    expect(copiedSecond.node.data.subflowGroupId).toBe('external-definition')
  })

  it('在顶层与嵌套分支之间移动完整块不会丢节点或生成重复标识', () => {
    const loop = createBlock('loop' as never)
    const nested = createBlock('print_log' as never)
    const tail = createBlock('click_element' as never)
    let blocks = insertAfter([loop], loop.id, tail)
    blocks = insertIntoContainer(blocks, loop.id, 'body', nested)
    blocks = moveBlockTo(blocks, tail.id, { mode: 'into', id: loop.id, slot: 'body' })
    const graph = generateGraphFromBlocks(blocks)
    expect(new Set(graph.nodes.map((node) => node.id)).size).toBe(3)
    const restored = parseGraphToBlocks(graph.nodes, graph.edges)
    expect(restored).toHaveLength(1)
    if (restored[0].kind !== 'loop') throw new Error('循环结构未恢复')
    expect(restored[0].body.map((block) => block.id)).toEqual([nested.id, tail.id])
  })
})
