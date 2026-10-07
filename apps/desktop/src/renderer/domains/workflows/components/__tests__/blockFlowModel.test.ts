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
  findEntryProblem,
  type Block,
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

  it('无限循环沿用循环体与完成端口', () => {
    const loop = createBlock('infinite_loop' as never)
    const body = createBlock('break_loop' as never)
    const blocks = insertIntoContainer([loop], loop.id, 'body', body)
    const { edges } = generateGraphFromBlocks(blocks)
    expect(loop.kind).toBe('loop')
    expect(edges).toContainEqual(expect.objectContaining({ source: loop.id, target: body.id, sourceHandle: 'loop' }))
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

describe('blockFlowModel 错误分支', () => {
  const withError = (kind: 'step' | 'condition' | 'loop') => {
    const source = createBlock(kind === 'step' ? ('click_element' as never) : (kind as never))
    const main = createBlock('print_log' as never)
    const handler = createBlock('print_log' as never)
    const handler2 = createBlock('print_log' as never)
    return { source, main, handler, handler2 }
  }
  const e = (source: string, target: string, sourceHandle?: string) =>
    ({ id: `${source}-${sourceHandle ?? 'd'}-${target}`, source, target, ...(sourceHandle ? { sourceHandle } : {}) })

  it('步骤块的错误边在图与模块条之间往返不丢失', () => {
    const { source, main, handler, handler2 } = withError('step')
    const nodes = [source, main, handler, handler2].map((b) => b.node)
    const edges = [e(source.id, main.id), e(source.id, handler.id, 'error'), e(handler.id, handler2.id)]
    const blocks = parseGraphToBlocks(nodes, edges)
    expect(blocks).toHaveLength(2)
    expect(blocks[0]).toMatchObject({ kind: 'step', id: source.id })
    expect((blocks[0] as Block & { onError?: Block[] }).onError?.map((b) => b.id)).toEqual([handler.id, handler2.id])

    const back = generateGraphFromBlocks(blocks)
    expect(back.nodes.map((n) => n.id).sort()).toEqual([source.id, main.id, handler.id, handler2.id].sort())
    expect(back.edges).toContainEqual(expect.objectContaining({ source: source.id, target: handler.id, sourceHandle: 'error' }))
    expect(back.edges).toContainEqual(expect.objectContaining({ source: source.id, target: main.id }))
    expect(back.edges).toContainEqual(expect.objectContaining({ source: handler.id, target: handler2.id }))
    // 错误处理链不会被接回主流程
    expect(back.edges.some((x) => x.source === handler2.id)).toBe(false)
    expect(parseGraphToBlocks(back.nodes, back.edges)).toEqual(blocks.map((b) => expect.objectContaining({ id: b.id })))
  })

  it('已知限制：同一节点的第二条错误出边、错误链回到主流程的边在往返后不保留', () => {
    const { source, main, handler, handler2 } = withError('step')
    const nodes = [source, main, handler, handler2].map((b) => b.node)
    const edges = [e(source.id, main.id), e(source.id, handler.id, 'error'), e(source.id, handler2.id, 'error'), e(handler.id, main.id)]
    const back = generateGraphFromBlocks(parseGraphToBlocks(nodes, edges))
    expect(back.edges.filter((x) => x.sourceHandle === 'error')).toHaveLength(1)
    expect(back.edges.some((x) => x.source === handler.id && x.target === main.id)).toBe(false)
    expect(back.nodes.map((n) => n.id)).toContain(handler2.id)
  })

  it('条件块与循环块同样保留错误边', () => {
    for (const kind of ['condition', 'loop'] as const) {
      const { source, handler } = withError(kind)
      const edges = [e(source.id, handler.id, 'error')]
      const blocks = parseGraphToBlocks([source.node, handler.node], edges)
      expect(blocks).toHaveLength(1)
      expect((blocks[0] as Block & { onError?: Block[] }).onError?.map((b) => b.id)).toEqual([handler.id])
      const back = generateGraphFromBlocks(blocks)
      expect(back.edges).toEqual([expect.objectContaining({ source: source.id, target: handler.id, sourceHandle: 'error' })])
    }
  })

  it('没有错误边的旧数据不产生 onError 字段', () => {
    const a = createBlock('print_log' as never)
    const b = createBlock('print_log' as never)
    const blocks = parseGraphToBlocks([a.node, b.node], [e(a.id, b.id)])
    expect(blocks.every((x) => !('onError' in x))).toBe(true)
    expect(generateGraphFromBlocks(blocks).edges).toEqual([
      expect.objectContaining({ id: `e-${a.id}-d-${b.id}`, source: a.id, target: b.id, type: 'smoothstep', animated: true }),
    ])
  })

  it('复制带错误分支的块时错误链节点获得新标识', () => {
    const { source, handler } = withError('step')
    const block = { ...source, onError: [handler] } as Block
    const copied = cloneBlock(block) as Block & { onError?: Block[] }
    expect(copied.onError).toHaveLength(1)
    expect(copied.onError![0].id).not.toBe(handler.id)
  })

  it('可向步骤块的错误分支插入并移动块', () => {
    const { source, handler } = withError('step')
    const blocks = insertIntoContainer([source], source.id, 'onError', handler)
    expect((blocks[0] as Block & { onError?: Block[] }).onError?.map((b) => b.id)).toEqual([handler.id])
  })
})

describe('findEntryProblem', () => {
  const mk = (id: string) => ({ ...createBlock('print_log' as never).node, id })
  const ed = (source: string, target: string, sourceHandle?: string) =>
    ({ id: `${source}-${target}`, source, target, ...(sourceHandle ? { sourceHandle } : {}) })

  it('完全循环的图没有起点', () => {
    const problem = findEntryProblem([mk('a'), mk('b')], [ed('a', 'b'), ed('b', 'a')])
    expect(problem?.code).toBe('NO_START_NODE')
    expect(problem?.message).toContain('没有可以开始的节点')
  })

  it('有入度为零的节点、空图、孤立节点都不报错', () => {
    expect(findEntryProblem([mk('a'), mk('b')], [ed('a', 'b')])).toBeNull()
    expect(findEntryProblem([], [])).toBeNull()
    expect(findEntryProblem([mk('a'), mk('b'), mk('c')], [ed('a', 'b'), ed('b', 'a')])).toBeNull()
  })

  it('错误边不计入普通入边', () => {
    // a 只被错误边指向：后端仍把它当起点
    expect(findEntryProblem([mk('a'), mk('b')], [ed('b', 'a', 'error'), ed('a', 'b')])).toBeNull()
    expect(findEntryProblem([mk('a'), mk('b')], [ed('b', 'a'), ed('a', 'b', 'error')])).toBeNull()
  })

  it('忽略不是模块节点的展示节点', () => {
    const note = { ...mk('n'), type: 'noteNode' }
    expect(findEntryProblem([mk('a'), mk('b'), note], [ed('a', 'b'), ed('b', 'a'), ed('n', 'a')])).not.toBeNull()
  })
})
