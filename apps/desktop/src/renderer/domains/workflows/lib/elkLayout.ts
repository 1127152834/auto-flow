// Source: WebRPA@5ccb900e, lib/elkLayout.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 统一图布局服务（基于 ELKJS）
 *
 * 画布"智能整理"、AI 小助手 auto_layout、模块条转流程图三处共用此服务，
 * 产出分层（layered）、无重叠、走线清晰的布局。
 *
 * 设计要点：
 * - 完全离线：使用 elkjs 的纯 JS 打包版 elk.bundled.js，模块级单例，不重复初始化。
 * - 默认 DOWN（自上而下），与"底部出→顶部入"的连线习惯、模块条纵向结构一致。
 * - 失败/超时一律向上抛出，由调用方回退（保持原坐标），绝不增删/破坏节点与连线。
 */
import ELK from 'elkjs/lib/elk.bundled.js'

export interface LayoutNodeInput {
  id: string
  width?: number
  height?: number
}

export interface LayoutEdgeInput {
  id: string
  source: string
  target: string
}

export interface LayoutOptions {
  /** 布局方向，默认 DOWN（自上而下） */
  direction?: 'DOWN' | 'RIGHT'
  /** 同层节点间距，默认 50 */
  nodeSpacing?: number
  /** 层间距，默认 70 */
  layerSpacing?: number
  /** 超时阈值（毫秒），默认 8000 */
  timeoutMs?: number
}

export interface LayoutResult {
  positions: Record<string, { x: number; y: number }>
}

/** 节点默认尺寸（与历史 auto_layout 常量一致） */
const DEFAULT_NODE_WIDTH = 220
const DEFAULT_NODE_HEIGHT = 80

// 模块级单例，避免每次调用/渲染重复初始化
let elkInstance: any = null
function getElk(): any {
  if (!elkInstance) {
    elkInstance = new (ELK as any)()
  }
  return elkInstance
}

function rejectAfter(ms: number): Promise<never> {
  return new Promise((_, reject) => {
    setTimeout(() => reject(new Error(`布局计算超时（>${ms}ms）`)), ms)
  })
}

/**
 * 计算图布局，返回各节点的新坐标。
 * 失败或超时时抛出异常，由调用方负责回退。
 */
export async function layoutGraph(
  nodes: LayoutNodeInput[],
  edges: LayoutEdgeInput[],
  options: LayoutOptions = {},
): Promise<LayoutResult> {
  const {
    direction = 'DOWN',
    nodeSpacing = 50,
    layerSpacing = 70,
    timeoutMs = 8000,
  } = options

  if (!nodes || nodes.length === 0) {
    return { positions: {} }
  }

  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': direction,
      'elk.layered.spacing.nodeNodeBetweenLayers': String(layerSpacing),
      'elk.spacing.nodeNode': String(nodeSpacing),
      'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
      'elk.edgeRouting': 'ORTHOGONAL',
    },
    children: nodes.map((n) => ({
      id: n.id,
      width: n.width && n.width > 0 ? n.width : DEFAULT_NODE_WIDTH,
      height: n.height && n.height > 0 ? n.height : DEFAULT_NODE_HEIGHT,
    })),
    // 仅传 source/target 参与分层；带 sourceHandle 的分支边在此只用 source/target 即可
    edges: edges.map((e) => ({
      id: e.id,
      sources: [e.source],
      targets: [e.target],
    })),
  }

  const elk = getElk()
  const result: any = await Promise.race([elk.layout(graph), rejectAfter(timeoutMs)])

  const positions: Record<string, { x: number; y: number }> = {}
  for (const child of result?.children || []) {
    if (typeof child.x === 'number' && typeof child.y === 'number') {
      positions[child.id] = { x: child.x, y: child.y }
    }
  }
  return { positions }
}
