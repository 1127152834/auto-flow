// Source: WebRPA@5ccb900e, components/workflow/SubflowMonitorDialog.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 子工作流执行监控窗口
 *
 * 「运行其它工作流」过去是后端静默跑完，父画布上只有一个节点在转，用户看不到子工作流
 * 内部执行到哪一步、卡在哪个模块。这里独立开一个窗口显示子工作流的画布并高亮当前模块，
 * 主画布保持不动（嵌套调用时每层各自一个窗口，用顶部标签切换）。
 *
 * 数据全部来自后端 subflow:* 事件，不读本地工作流文件——运行中的才是事实。
 */
import { useEffect, useMemo, useState } from 'react'
import { X, Loader2, CheckCircle2, XCircle, Minimize2 } from 'lucide-react'
import { ReactFlow, Background, Controls, MarkerType, type Node, type Edge } from '@xyflow/react'
import { socketService } from '../events'
import { moduleTypeLabels } from '../editor-store'
import { cn } from '../lib/utils'

/** 后端 subflow:started 推来的精简图结构 */
interface SubflowNodePayload {
  id: string
  moduleType: string
  label: string
  position: { x: number; y: number }
  width?: number | null
  height?: number | null
}

interface SubflowEdgePayload {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
}

type NodeRunState = 'idle' | 'running' | 'success' | 'failed'

interface SubflowSession {
  subflowId: string
  name: string
  file?: string
  depth: number
  nodes: SubflowNodePayload[]
  edges: SubflowEdgePayload[]
  /** 每个节点的运行状态，驱动高亮 */
  nodeStates: Record<string, NodeRunState>
  status: 'running' | 'success' | 'failed'
  executedNodes?: number
  failedNodes?: number
  error?: string | null
  /** 最近一条日志，显示在底部状态条 */
  lastLog?: string
}

const MAX_SESSIONS = 8

/** 后端未给出名称时的兜底显示名 */
const FALLBACK_NAME = '子工作流'
/** 嵌套层级标签前缀（单独抽出，避免中文进模板字符串后无法整句翻译） */
const DEPTH_LABEL = '嵌套层级'

export function SubflowMonitorDialog() {
  const [sessions, setSessions] = useState<SubflowSession[]>([])
  const [activeId, setActiveId] = useState<string>('')
  const [minimized, setMinimized] = useState(false)

  useEffect(() => {
    const offStarted = socketService.onSubflowEvent('subflow:started', (data) => {
      const session: SubflowSession = {
        subflowId: String(data.subflowId || ''),
        name: String(data.name || FALLBACK_NAME),
        file: data.file ? String(data.file) : undefined,
        depth: Number(data.depth || 0),
        nodes: (data.nodes || []) as SubflowNodePayload[],
        edges: (data.edges || []) as SubflowEdgePayload[],
        nodeStates: {},
        status: 'running',
      }
      if (!session.subflowId) return
      setSessions((prev) => {
        // 同 id 重复推送时覆盖，避免重复窗口；超上限丢最旧的，防止长链把内存吃满
        const rest = prev.filter((s) => s.subflowId !== session.subflowId)
        return [...rest, session].slice(-MAX_SESSIONS)
      })
      setActiveId(session.subflowId)
      setMinimized(false)
    })

    const offNodeStart = socketService.onSubflowEvent('subflow:node_start', (data) => {
      const id = String(data.subflowId || '')
      const nodeId = String(data.nodeId || '')
      setSessions((prev) => prev.map((s) => (
        s.subflowId === id
          ? { ...s, nodeStates: { ...s.nodeStates, [nodeId]: 'running' } }
          : s
      )))
    })

    const offNodeComplete = socketService.onSubflowEvent('subflow:node_complete', (data) => {
      const id = String(data.subflowId || '')
      const nodeId = String(data.nodeId || '')
      const ok = Boolean(data.success)
      setSessions((prev) => prev.map((s) => (
        s.subflowId === id
          ? { ...s, nodeStates: { ...s.nodeStates, [nodeId]: ok ? 'success' : 'failed' } }
          : s
      )))
    })

    const offLog = socketService.onSubflowEvent('subflow:log', (data) => {
      const id = String(data.subflowId || '')
      const msg = String(data.message || '')
      if (!msg) return
      setSessions((prev) => prev.map((s) => (s.subflowId === id ? { ...s, lastLog: msg } : s)))
    })

    const offCompleted = socketService.onSubflowEvent('subflow:completed', (data) => {
      const id = String(data.subflowId || '')
      setSessions((prev) => prev.map((s) => (
        s.subflowId === id
          ? {
              ...s,
              status: data.success ? 'success' : 'failed',
              executedNodes: Number(data.executedNodes || 0),
              failedNodes: Number(data.failedNodes || 0),
              error: data.error ? String(data.error) : null,
            }
          : s
      )))
    })

    return () => {
      offStarted()
      offNodeStart()
      offNodeComplete()
      offLog()
      offCompleted()
    }
  }, [])

  const active = useMemo(
    () => sessions.find((s) => s.subflowId === activeId) || sessions[sessions.length - 1],
    [sessions, activeId],
  )

  // 把后端精简结构转成 ReactFlow 节点，用运行状态决定描边/背景（高亮当前模块）
  const flowNodes: Node[] = useMemo(() => {
    if (!active) return []
    return active.nodes.map((n) => {
      const state = active.nodeStates[n.id] || 'idle'
      const label = n.label || moduleTypeLabels[n.moduleType as keyof typeof moduleTypeLabels] || n.moduleType
      return {
        id: n.id,
        position: n.position,
        data: { label },
        type: 'default',
        draggable: false,
        selectable: false,
        style: {
          width: n.width || 180,
          fontSize: 12,
          borderRadius: 'var(--radius-card)',
          padding: 8,
          borderWidth: state === 'idle' ? 1 : 2,
          borderStyle: 'solid',
          transition: 'box-shadow .2s, border-color .2s',
          ...(state === 'running'
            ? {
                borderColor: 'hsl(var(--brand-600))',
                background: 'hsl(var(--brand-50))',
                boxShadow: '0 0 0 4px hsl(var(--brand-600) / 0.18)',
                animation: 'webrpa-subflow-pulse 1.1s ease-in-out infinite',
              }
            : state === 'success'
            ? { borderColor: 'hsl(var(--success-500))', background: 'hsl(var(--success-50))' }
            : state === 'failed'
            ? { borderColor: 'hsl(var(--destructive))', background: 'hsl(var(--destructive) / 0.08)' }
            : { borderColor: 'hsl(var(--border))', background: 'hsl(var(--background))' }),
        },
      }
    })
  }, [active])

  const flowEdges: Edge[] = useMemo(() => {
    if (!active) return []
    return active.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle || undefined,
      targetHandle: e.targetHandle || undefined,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: 'hsl(var(--border))' },
    }))
  }, [active])

  if (sessions.length === 0 || !active) return null

  const runningCount = Object.values(active.nodeStates).filter((s) => s === 'running').length
  const doneCount = Object.values(active.nodeStates).filter((s) => s === 'success' || s === 'failed').length

  if (minimized) {
    return (
      <button
        onClick={() => setMinimized(false)}
        className="fixed bottom-4 right-4 z-[70] flex items-center gap-2 px-3 py-2 rounded-lg shadow-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] text-xs"
        title="展开子工作流监控"
      >
        {active.status === 'running' ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-[hsl(var(--brand-600))]" />
        ) : active.status === 'success' ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-[hsl(var(--success-500))]" />
        ) : (
          <XCircle className="w-3.5 h-3.5 text-[hsl(var(--destructive))]" />
        )}
        子工作流：{active.name}
      </button>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 z-[70] w-[560px] max-w-[92vw] h-[420px] max-h-[70vh] flex flex-col rounded-xl shadow-2xl border border-[hsl(var(--border))] bg-[hsl(var(--background))] overflow-hidden">
      {/* 标题栏 */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[hsl(var(--border))] bg-[hsl(var(--muted))]">
        {active.status === 'running' ? (
          <Loader2 className="w-4 h-4 animate-spin text-[hsl(var(--brand-600))] shrink-0" />
        ) : active.status === 'success' ? (
          <CheckCircle2 className="w-4 h-4 text-[hsl(var(--success-500))] shrink-0" />
        ) : (
          <XCircle className="w-4 h-4 text-[hsl(var(--destructive))] shrink-0" />
        )}
        <span className="text-sm font-medium truncate flex-1" title={active.file || active.name}>
          子工作流：{active.name}
        </span>
        <span className="text-[11px] text-[hsl(var(--muted-foreground))] shrink-0">
          {doneCount}/{active.nodes.length}
        </span>
        <button
          onClick={() => setMinimized(true)}
          className="p-1 rounded hover:bg-[hsl(var(--background))]"
          title="最小化"
        >
          <Minimize2 className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => setSessions((prev) => prev.filter((s) => s.subflowId !== active.subflowId))}
          className="p-1 rounded hover:bg-[hsl(var(--background))]"
          title="关闭（不影响执行）"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 嵌套调用时的层级标签 */}
      {sessions.length > 1 && (
        <div className="flex items-center gap-1 px-2 py-1.5 border-b border-[hsl(var(--border))] overflow-x-auto">
          {sessions.map((s) => (
            <button
              key={s.subflowId}
              onClick={() => setActiveId(s.subflowId)}
              className={cn(
                'px-2 py-0.5 text-[11px] rounded whitespace-nowrap border',
                s.subflowId === active.subflowId
                  ? 'bg-[hsl(var(--brand-50))] border-[hsl(var(--brand-600)/0.3)] text-[hsl(var(--brand-600))]'
                  : 'bg-transparent border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))]',
              )}
              title={DEPTH_LABEL + ' ' + (s.depth + 1)}
            >
              {s.depth > 0 && <span className="opacity-60">↳ </span>}
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* 只读画布：运行到哪个模块就高亮哪个 */}
      <div className="flex-1 min-h-0">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {/* 状态条 */}
      <div className="px-3 py-1.5 border-t border-[hsl(var(--border))] text-[11px] text-[hsl(var(--muted-foreground))] truncate">
        {active.status === 'running'
          ? active.lastLog || (runningCount > 0 ? '正在执行…' : '准备中…')
          : active.status === 'success'
          ? `执行完成，共 ${active.executedNodes ?? active.nodes.length} 个模块`
          : `执行失败：${active.error || '未知错误'}`}
      </div>
    </div>
  )
}
