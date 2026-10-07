import { useEffect, useRef, type RefObject } from 'react'
import type { Connection, Node } from '@xyflow/react'
import { useNodeRunStore } from '../hooks/stores/nodeRunStore'

export interface ConnectSource {
  nodeId: string
  handleId: string | null
}

interface ConnectEndState {
  fromHandle?: { nodeId: string; id?: string | null; type: 'source' | 'target' } | null
  toNode?: unknown
  toHandle?: unknown
}

/** 仅当连线从 source 句柄出发并释放在空白画布时，返回需要自动连线的来源 */
export function resolveDragOutSource(state: ConnectEndState): ConnectSource | null {
  const from = state.fromHandle
  if (!from || from.type !== 'source' || state.toNode || state.toHandle) return null
  return { nodeId: from.nodeId, handleId: from.id ?? null }
}

export function connectToNewNode(source: ConnectSource, targetId: string, onConnect: (c: Connection) => void) {
  onConnect({ source: source.nodeId, sourceHandle: source.handleId, target: targetId, targetHandle: null })
}

/** 失败平移时长：full 用 --motion-slow（280ms），reduce/off 为 0 */
export function failurePanDuration(motion: string | undefined = document.documentElement.dataset.motion): number {
  return motion === 'reduce' || motion === 'off' ? 0 : 280
}

interface CenterTarget {
  setCenter: (x: number, y: number, o: { zoom: number; duration: number }) => unknown
  getViewport: () => { zoom: number }
}

/** 运行失败时把失败节点平移到视野中心一次；用户之后手动平移/缩放则不再定位同一次失败 */
export function useFailureFocus(
  instance: RefObject<CenterTarget | null>,
  nodes: Node[],
  executionStatus: string,
) {
  const statuses = useNodeRunStore((s) => s.statuses)
  const panned = useRef(false)
  const userMoved = useRef(false)
  const frame = useRef<number | null>(null)
  const statusRef = useRef(executionStatus)
  statusRef.current = executionStatus

  useEffect(() => {
    if (executionStatus !== 'failed') {
      panned.current = false
      userMoved.current = false
      return
    }
    if (panned.current || userMoved.current || !instance.current) return
    const failedId = Object.keys(statuses).find((id) => statuses[id] === 'failed')
    const node = failedId ? nodes.find((n) => n.id === failedId) : undefined
    if (!node) return
    panned.current = true
    const center = { x: node.position.x + (node.width || 200) / 2, y: node.position.y + (node.height || 100) / 2 }
    // 运行结束时底部面板可能同时收起、画布尺寸随之变化；等两帧让画布量好新尺寸再居中
    frame.current = requestAnimationFrame(() => {
      frame.current = requestAnimationFrame(() => {
        frame.current = null
        const target = instance.current
        if (target) target.setCenter(center.x, center.y, { zoom: target.getViewport().zoom, duration: failurePanDuration() })
      })
    })
  }, [executionStatus, statuses, nodes, instance])

  useEffect(() => () => { if (frame.current !== null) cancelAnimationFrame(frame.current) }, [])

  /** 传给 ReactFlow onMoveStart：event 非空才是用户操作；只有失败之后的操作才抑制这次定位 */
  return (event: unknown) => { if (event && statusRef.current === 'failed') userMoved.current = true }
}
