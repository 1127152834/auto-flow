import { useEffect, useMemo, useRef } from 'react'
import { Background, BackgroundVariant, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps, type ReactFlowInstance } from '@xyflow/react'
import { BracketsCurly, Camera, CursorClick, Globe, TextT, Timer, WarningCircle } from '@phosphor-icons/react'
import '@xyflow/react/dist/style.css'
import type { NodeDefinition, Point, WorkflowContent, WorkflowIssue } from '../types'

type CanvasNode = Node<{ label: string; title: string; kind: string; summary: string; issueCount: number; runStatus?: string }, 'workflow'>
const icons = { open_page: Globe, click_element: CursorClick, input_text: TextT, wait_element: Timer, get_element_info: BracketsCurly, screenshot: Camera }
function WorkflowNodeView({ data, selected }: NodeProps<CanvasNode>) {
  const Icon = icons[data.kind as keyof typeof icons] ?? Globe
  return <div className={`w-[220px] rounded-card border bg-surface shadow-sm transition-shadow ${selected ? 'border-clay shadow-[0_0_0_2px_var(--color-clay-soft)]' : 'border-line'}`}>
    <Handle type="target" position={Position.Left} id="in" className="!h-3 !w-3 !border-2 !border-surface !bg-clay" />
    <div className="flex items-start gap-3 p-3.5"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-clay-soft text-clay"><Icon size={19} /></span><div className="min-w-0"><div className="truncate text-sm font-semibold text-ink">{data.label || data.title}</div><p className="mt-1 truncate text-[11px] text-muted">{data.summary || data.title}</p></div></div>
    {data.issueCount > 0 ? <div className="flex items-center gap-1.5 border-t border-line px-3.5 py-2 text-[11px] text-amber-800"><WarningCircle size={13} />{data.issueCount} 项待配置</div> : null}
    {data.runStatus ? <div role="status" className={`border-t border-line px-3.5 py-2 text-[11px] ${data.runStatus === '失败' ? 'text-red-700' : 'text-clay'}`}>{data.runStatus}</div> : null}
    <Handle type="source" position={Position.Right} id="out" className="!h-3 !w-3 !border-2 !border-surface !bg-clay" />
  </div>
}
const nodeTypes = { workflow: WorkflowNodeView }

export type WorkflowCanvasProps = {
  content: WorkflowContent; catalog: NodeDefinition[]; issues: WorkflowIssue[]
  selectedNodes: string[]; selectedEdges: string[]; disabled?: boolean
  runMarkers?: Record<string, string>
  locate?: { nodeId: string; request: number } | null
  onSelect(nodes: string[] | null, edges: string[] | null): void
  onMove(positions: Record<string, Point>): void
  onViewport(viewport: WorkflowContent['layout']['viewport']): void
  onConnect(source: string, target: string): void
  onAdd(type: string, point: Point): void
  onEditStart(): void; onEditEnd(): void
  onPointer(point: Point): void
}

export function WorkflowCanvas(props: WorkflowCanvasProps) {
  const { content, catalog, issues, selectedNodes, selectedEdges, disabled, runMarkers, locate, onSelect, onMove, onViewport, onConnect, onAdd, onEditStart, onEditEnd, onPointer } = props
  const instance = useRef<ReactFlowInstance<CanvasNode, Edge> | null>(null)
  const nodes = useMemo<CanvasNode[]>(() => content.document.nodes.map(node => ({
    id: node.id, type: 'workflow', position: content.layout.nodes[node.id], selected: selectedNodes.includes(node.id),
    ariaLabel: `节点：${node.label || node.type}`, data: {
      label: node.label, title: catalog.find(item => item.type === node.type)?.title ?? node.type, kind: node.type,
      summary: String(node.config.url || node.config.selector || (node.type === 'screenshot' ? '网页截图' : '')),
      issueCount: issues.filter(issue => issue.nodeId === node.id).length,
      runStatus: runMarkers?.[node.id],
    },
  })), [content, catalog, issues, selectedNodes, runMarkers])
  const edges = useMemo<Edge[]>(() => content.document.edges.map(edge => ({ ...edge, selected: selectedEdges.includes(edge.id), style: { stroke: selectedEdges.includes(edge.id) ? '#a2684a' : '#989087', strokeWidth: 2 } })), [content.document.edges, selectedEdges])
  useEffect(() => { if (locate && instance.current) void instance.current.fitView({ nodes: [{ id: locate.nodeId }], duration: 250, maxZoom: 1, padding: 1 }) }, [locate])

  return <div className="relative h-full min-h-[320px] flex-1 bg-canvas" aria-label="工作流画布">
    <ReactFlow<CanvasNode, Edge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} onInit={flow => { instance.current = flow }}
      defaultViewport={content.layout.viewport} onMoveEnd={(_event, viewport) => onViewport(viewport)}
      onNodeDragStart={onEditStart} onNodeDragStop={onEditEnd} onSelectionDragStart={onEditStart} onSelectionDragStop={onEditEnd}
      onNodesChange={changes => { if (disabled) return; const positions: Record<string, Point> = {}; const selection = new Set(selectedNodes); let changedSelection = false; for (const change of changes) { if (change.type === 'position' && change.position) positions[change.id] = change.position; if (change.type === 'select') { changedSelection = true; if (change.selected) selection.add(change.id); else selection.delete(change.id) } }; if (Object.keys(positions).length) onMove(positions); if (changedSelection) onSelect([...selection], null) }}
      onEdgesChange={changes => { if (disabled) return; const selection = new Set(selectedEdges); let changed = false; for (const change of changes) if (change.type === 'select') { changed = true; if (change.selected) selection.add(change.id); else selection.delete(change.id) }; if (changed) onSelect(null, [...selection]) }}
      onConnect={connection => { if (!disabled && connection.source && connection.target) onConnect(connection.source, connection.target) }}
      onPaneClick={() => onSelect([], [])}
      onDragOver={event => { if (event.dataTransfer.types.includes('application/autoflow-node')) { event.preventDefault(); event.dataTransfer.dropEffect = 'copy' } }}
      onDrop={event => { const type = event.dataTransfer.getData('application/autoflow-node'); if (!disabled && type && instance.current) { event.preventDefault(); onAdd(type, instance.current.screenToFlowPosition({ x: event.clientX, y: event.clientY })) } }}
      onMouseMove={event => { if (instance.current) onPointer(instance.current.screenToFlowPosition({ x: event.clientX, y: event.clientY })) }}
      nodesDraggable={!disabled} nodesConnectable={!disabled} elementsSelectable={!disabled} deleteKeyCode={null}
      selectionOnDrag panOnDrag={[1, 2]} multiSelectionKeyCode={['Meta', 'Control', 'Shift']} selectionKeyCode="Shift"
      minZoom={0.25} maxZoom={2} proOptions={{ hideAttribution: true }}>
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#cec8bf" />
      <Controls showInteractive={false} aria-label="画布视图控制" />
    </ReactFlow>
    {!nodes.length ? <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3 text-center"><span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-line bg-surface text-clay"><Globe size={26} /></span><h2 className="text-lg font-semibold text-ink">从第一个步骤开始</h2><p className="max-w-xs text-sm leading-6 text-muted">从左侧添加或拖入节点，连接步骤后配置参数。<br />也可以打开已经保存的流程。</p></div> : null}
  </div>
}
