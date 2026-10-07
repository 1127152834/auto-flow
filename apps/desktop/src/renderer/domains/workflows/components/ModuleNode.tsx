// Source: WebRPA@5ccb900e, components/workflow/ModuleNode.tsx; see SOURCE.md for license and adaptation boundaries.
import { memo } from 'react'
import { Handle, Position, type NodeProps, useReactFlow } from '@xyflow/react'
import { cn } from '../lib/utils'
import { getNodeConfigData, type NodeData } from '../editor-store'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
import { Globe, ExternalLink, LocateFixed, Play, Loader2, CheckCircle2, XCircle, SkipForward, AlertTriangle } from 'lucide-react'
import { moduleIcons, excludedModuleTypes } from './ModuleSidebar'
import { getBlockRowColorClasses } from './moduleColors'
import { useNodeIssues } from '../lib/nodeIssues'
import { useNodeRunStore } from '../hooks/stores/nodeRunStore'
import { useDebugStore } from '../hooks/stores/debugStore'

const RING_KEYFRAMES_ID = 'af-node-ring-keyframes'
// 运行外圈关键帧：全局样式不归本步骤所有，先在此注入一次（data-motion=reduce/off 下由 [style*="infinite"] 规则压制为静态环）
function ensureRingKeyframes() {
  if (typeof document === 'undefined' || document.getElementById(RING_KEYFRAMES_ID)) return
  const style = document.createElement('style')
  style.id = RING_KEYFRAMES_ID
  style.textContent = '@keyframes af-node-ring{0%,100%{opacity:.35}50%{opacity:1}}'
  document.head.appendChild(style)
}
ensureRingKeyframes()

const STATUS_BADGES = {
  running: { Icon: Loader2, label: '运行中', className: 'bg-info-soft text-info' },
  success: { Icon: CheckCircle2, label: '已完成', className: 'bg-success-soft text-success' },
  failed: { Icon: XCircle, label: '运行失败', className: 'bg-danger-soft text-danger' },
  skipped: { Icon: SkipForward, label: '已跳过', className: 'bg-surface-subtle text-muted' },
} as const

function ModuleNodeComponent({ id, data, selected }: NodeProps) {
  const rawNodeData = data as NodeData
  const nodeData = getNodeConfigData(rawNodeData)
  const { fitView, getNodes, setCenter } = useReactFlow()
  const runStatus = useNodeRunStore((s) => s.statuses[id]) as keyof typeof STATUS_BADGES | undefined
  const issues = useNodeIssues(id)
  const hasBreakpoint = useDebugStore((s) => s.breakpoints.has(id))
  const isPausedHere = useDebugStore((s) => s.isPaused && s.pausedNodeId === id)
  const toggleBreakpoint = useDebugStore((s) => s.toggleBreakpoint)
  const isDisabled = rawNodeData.disabled === true
  const isHighlighted = rawNodeData.isHighlighted === true
  const handleSize = useGlobalConfigStore((state) => state.config.display?.handleSize || 12)

  // 对于自定义模块，使用节点数据中的图标和颜色
  const isCustomModule = nodeData.moduleType === 'custom_module'
  const customIcon = isCustomModule ? (nodeData.icon as string) : null
  const customColor = isCustomModule ? (nodeData.color as string) : null
  
  const Icon = isCustomModule ? null : (moduleIcons[nodeData.moduleType] || Globe)
  // 兜底样式统一走 moduleColors 的 DEFAULT_NODE_COLOR_CLASS，不在此处硬编码字面量（需求 4.6）
  const accentBorderClass = isCustomModule ? '' : getBlockRowColorClasses(nodeData.moduleType).borderClass
  const statusBadge = runStatus ? STATUS_BADGES[runStatus] : undefined
  const issueText = issues.map((issue) => issue.message).join('；')

  const handleSubflowDoubleClick = (e: React.MouseEvent) => {
    if (nodeData.moduleType !== 'subflow') return
    e.stopPropagation()
    const subflowName = nodeData.subflowName as string
    if (!subflowName) return
    const nodes = getNodes()
    const targetNode = nodes.find(n => {
      const config = getNodeConfigData(n.data as NodeData)
      return (n.type === 'subflowHeaderNode' && config.subflowName === subflowName) ||
        (n.type === 'groupNode' && config.isSubflow && config.subflowName === subflowName)
    })
    if (targetNode) {
      if (targetNode.type === 'groupNode') {
        // 分组节点用 setCenter 定位到中心
        const w = (targetNode.data.width as number) || (targetNode.width as number) || 400
        const h = (targetNode.data.height as number) || (targetNode.height as number) || 300
        const cx = targetNode.position.x + w / 2
        const cy = targetNode.position.y + h / 2
        setCenter(cx, cy, { duration: 500, zoom: 0.8 })
      } else {
        fitView({ nodes: [targetNode], duration: 500, padding: 0.3 })
      }
      setTimeout(() => {
        const event = new CustomEvent('highlight-node', { detail: { nodeId: targetNode.id } })
        window.dispatchEvent(event)
      }, 100)
    }
  }

  const getSummary = () => {
    if (nodeData.moduleType === 'subflow' && nodeData.subflowName) return `${nodeData.subflowName}`
    if (nodeData.url) return nodeData.url as string
    if (nodeData.selector) return nodeData.selector as string
    if (nodeData.text) return nodeData.text as string
    if (nodeData.logMessage) return nodeData.logMessage as string
    if (nodeData.variableName) return `→ ${nodeData.variableName}`
    if (nodeData.userPrompt) return nodeData.userPrompt as string
    if (nodeData.requestUrl) return nodeData.requestUrl as string
    return ''
  }

  const truncateText = (text: string, maxLen: number) =>
    text.length <= maxLen ? text : text.slice(0, maxLen) + '...'

  const summary = truncateText(getSummary(), 30)
  const customName = rawNodeData.name as string | undefined
  const isSubflow = nodeData.moduleType === 'subflow'

  return (
    <div
      className={cn(
        'group relative pl-5 pr-4 py-3 rounded-card border-[1.5px] border-line bg-surface text-ink min-w-[180px] max-w-[280px]',
        // 关键：只 transition 不会引起 reflow / 影响 RF 计算 handle 的属性
        'shadow-soft hover:shadow-pop-lg hover:border-[hsl(var(--brand-500)/0.6)]',
        'transition-[box-shadow,border-color] duration-150 ease-out',
        isDisabled && 'bg-disabled-surface text-disabled-ink opacity-70',
        selected && '!border-[hsl(var(--brand-500))] !shadow-pop-lg ring-2 ring-[hsl(var(--brand-500)/0.4)]',
        isHighlighted && '!border-[hsl(var(--warning-500))] ring-2 ring-[hsl(var(--warning-500)/0.5)]',
        // 执行态：运行中只有外圈进度元素；成功/失败只变色，不带动画
        runStatus === 'running' && '!border-info',
        runStatus === 'success' && '!border-success ring-2 ring-success/45',
        runStatus === 'failed' && '!border-danger ring-2 ring-danger/50',
        isPausedHere && '!border-warning ring-2 ring-warning/70 shadow-warning-glow',
        isSubflow && nodeData.subflowName ? 'cursor-pointer' : '',
        // AI 助手可视化搭建时节点入场动画
        (nodeData as any).__aiSpawning && 'ai-node-spawn'
      )}
      data-testid="module-node"
      style={isDisabled ? { opacity: 0.6 } : undefined}
      onDoubleClick={isSubflow && nodeData.subflowName ? handleSubflowDoubleClick : undefined}
    >
      <div
        data-testid="node-accent-bar"
        className={cn('pointer-events-none absolute inset-y-0 left-0 rounded-l-card border-l-4', accentBorderClass)}
        style={customColor ? { borderLeftColor: customColor } : undefined}
      />
      {runStatus === 'running' && (
        <div
          data-testid="node-run-ring"
          className="pointer-events-none absolute -inset-[3px] rounded-card border-2 border-info"
          style={{ animation: 'af-node-ring var(--motion-loop) var(--ease-standard) infinite' }}
        />
      )}
      {excludedModuleTypes.has(nodeData.moduleType) && <div role="status" className="text-xs bg-warning-soft text-warning-strong px-2 py-1">此节点已排除，保留原配置，仅供查看和导出</div>}
      {/* 断点圆点：点击切换。命中时实心红，未命中时悬停才显形 */}
      <button
        className={cn(
          'nodrag nopan absolute -left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full border-2 border-surface shadow z-10 transition-opacity duration-150 cursor-pointer',
          hasBreakpoint ? 'bg-danger opacity-100' : 'bg-danger/40 opacity-0 group-hover:opacity-100 hover:!bg-danger'
        )}
        title={hasBreakpoint ? '移除断点' : '设置断点（运行到此暂停）'}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => { e.stopPropagation(); toggleBreakpoint(id) }}
      />

      {/* 从此节点开始运行：悬停显现的绿色播放按钮（调试用，跳过其上游节点） */}
      <button
        className={cn(
          'nodrag nopan absolute -left-2 -top-2 w-5 h-5 flex items-center justify-center rounded-full bg-success text-on-accent shadow ring-2 ring-surface z-10 cursor-pointer',
          'opacity-0 group-hover:opacity-100 hover:scale-110 hover:bg-success-strong transition-all duration-150'
        )}
        title="从此节点开始运行（跳过其上游节点）"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          window.dispatchEvent(new CustomEvent('run-from-node', { detail: { nodeId: id } }))
        }}
      >
        <Play className="w-2.5 h-2.5" strokeWidth={3} fill="currentColor" />
      </button>

      <button
        className="nodrag nopan absolute left-5 -top-2 w-5 h-5 flex items-center justify-center rounded-full bg-warning text-on-accent shadow ring-2 ring-surface z-10 cursor-pointer opacity-0 group-hover:opacity-100 hover:scale-110 hover:bg-warning-strong transition-all duration-150"
        title="运行至此节点（保留前置上下文）"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation()
          window.dispatchEvent(new CustomEvent('run-to-node', { detail: { nodeId: id } }))
        }}
      >
        <LocateFixed className="w-2.5 h-2.5" strokeWidth={3} />
      </button>

      {isDisabled && (
        <div className="absolute -top-2 -right-2 bg-[hsl(var(--slate-700))] text-white text-xs font-bold px-2 py-0.5 rounded-control shadow-md tracking-wider">
          已禁用
        </div>
      )}

      {/* 子流程跳转图标 */}
      {isSubflow && nodeData.subflowName && (
        <button
          className="absolute -top-2 -right-2 w-6 h-6 flex items-center justify-center bg-gradient-to-br from-[hsl(var(--success-500))] to-[hsl(var(--success-700))] text-white rounded-full shadow-success-glow ring-2 ring-surface cursor-pointer hover:scale-110 transition-transform duration-150"
          title="跳转到子流程定义"
          onClick={(e) => {
            e.stopPropagation()
            handleSubflowDoubleClick(e as unknown as React.MouseEvent)
          }}
        >
          <ExternalLink className="w-3 h-3" strokeWidth={2.5} />
        </button>
      )}

      {/* 输入连接点 */}
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-[hsl(var(--card))] !border-[2px] !border-[hsl(var(--brand-500))]"
        style={{ width: `${handleSize}px`, height: `${handleSize}px` }}
      />

      {/* 节点内容 */}
      <div className="flex items-center gap-2 relative">
        <div className="shrink-0">
          {isCustomModule && customIcon ? (
            <span className="text-2xl">{customIcon}</span>
          ) : Icon ? (
            <Icon className="w-5 h-5 text-current" />
          ) : (
            <Globe className="w-5 h-5 text-current" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm truncate">
            {nodeData.label}
            {customName && (
              <span className="text-warning font-normal ml-1">
                ({customName})
              </span>
            )}
          </div>
          {summary && (
            <div className={cn(
              'text-[13px] truncate mt-0.5',
              isSubflow && nodeData.subflowName ? 'text-success font-bold' : 'text-muted'
            )}>
              {summary}
            </div>
          )}
        </div>
        {(issues.length > 0 || statusBadge) && (
          <div className="flex shrink-0 items-center gap-1">
            {issues.length > 0 && (
              <span
                role="img"
                data-testid="node-issue-badge"
                aria-label={issueText}
                title={issueText}
                className="flex h-5 w-5 items-center justify-center rounded-full bg-warning-soft text-warning"
              >
                <AlertTriangle className="h-3.5 w-3.5" />
              </span>
            )}
            {statusBadge && (
              <span
                role="img"
                data-testid="node-status-badge"
                aria-label={statusBadge.label}
                title={statusBadge.label}
                className={cn('flex h-5 w-5 items-center justify-center rounded-full', statusBadge.className)}
              >
                <statusBadge.Icon className="h-3.5 w-3.5" />
              </span>
            )}
          </div>
        )}
      </div>

      {/* 输出连接点 */}
      {nodeData.moduleType === 'condition' ||
       nodeData.moduleType === 'face_recognition' ||
       nodeData.moduleType === 'element_exists' ||
       nodeData.moduleType === 'element_visible' ||
       nodeData.moduleType === 'image_exists' ||
       nodeData.moduleType === 'phone_image_exists' ||
       nodeData.moduleType === 'probability_trigger' ? (
        <>
          <Handle type="source" position={Position.Bottom} id={nodeData.moduleType === 'probability_trigger' ? 'path1' : 'true'}
            className="!bg-[hsl(var(--success-500))] !border-[2px] !border-surface shadow-success-glow" style={{ left: '30%', width: `${handleSize}px`, height: `${handleSize}px` }} />
          <div className="absolute -bottom-6 px-1.5 py-0.5 rounded-control bg-[hsl(var(--success-50))] text-[hsl(var(--success-700))] border border-[hsl(var(--success-500)/0.3)] text-xs font-bold shadow-xs whitespace-nowrap" style={{ left: '30%', transform: 'translateX(-50%)' }}>
            {nodeData.moduleType === 'probability_trigger' ? '路径1' : nodeData.moduleType === 'face_recognition' ? '匹配' : nodeData.moduleType === 'element_visible' ? '可见' : nodeData.moduleType === 'element_exists' || nodeData.moduleType === 'image_exists' || nodeData.moduleType === 'phone_image_exists' ? '存在' : '是'}
          </div>
          <Handle type="source" position={Position.Bottom} id={nodeData.moduleType === 'probability_trigger' ? 'path2' : 'false'}
            className="!bg-[hsl(var(--danger-500))] !border-[2px] !border-surface shadow-danger-glow" style={{ left: '70%', width: `${handleSize}px`, height: `${handleSize}px` }} />
          <div className="absolute -bottom-6 px-1.5 py-0.5 rounded-control bg-[hsl(var(--danger-50))] text-[hsl(var(--danger-700))] border border-[hsl(var(--danger-500)/0.3)] text-xs font-bold shadow-xs whitespace-nowrap" style={{ left: '70%', transform: 'translateX(-50%)' }}>
            {nodeData.moduleType === 'probability_trigger' ? '路径2' : nodeData.moduleType === 'face_recognition' ? '不匹配' : nodeData.moduleType === 'element_visible' ? '不可见' : nodeData.moduleType === 'element_exists' || nodeData.moduleType === 'image_exists' || nodeData.moduleType === 'phone_image_exists' ? '不存在' : '否'}
          </div>
          <Handle type="source" position={Position.Right} id="error" className="!bg-[hsl(var(--warning-500))] !border-[2px] !border-surface" style={{ top: '50%', width: `${handleSize * 0.83}px`, height: `${handleSize * 0.83}px` }} />
        </>
      ) : nodeData.moduleType === 'loop' || nodeData.moduleType === 'infinite_loop' || nodeData.moduleType === 'foreach' || nodeData.moduleType === 'foreach_dict' ? (
        <>
          <Handle type="source" position={Position.Bottom} id="loop" className="!bg-[hsl(var(--success-500))] !border-[2px] !border-surface" style={{ left: '30%', width: `${handleSize}px`, height: `${handleSize}px` }} />
          <div className="absolute -bottom-6 px-1.5 py-0.5 rounded-control bg-[hsl(var(--success-50))] text-[hsl(var(--success-700))] border border-[hsl(var(--success-500)/0.3)] text-xs font-bold shadow-xs whitespace-nowrap" style={{ left: '30%', transform: 'translateX(-50%)' }}>循环</div>
          <Handle type="source" position={Position.Bottom} id="done" className="!bg-[hsl(var(--danger-500))] !border-[2px] !border-surface" style={{ left: '70%', width: `${handleSize}px`, height: `${handleSize}px` }} />
          <div className="absolute -bottom-6 px-1.5 py-0.5 rounded-control bg-[hsl(var(--danger-50))] text-[hsl(var(--danger-700))] border border-[hsl(var(--danger-500)/0.3)] text-xs font-bold shadow-xs whitespace-nowrap" style={{ left: '70%', transform: 'translateX(-50%)' }}>完成</div>
          <Handle type="source" position={Position.Right} id="error" className="!bg-[hsl(var(--warning-500))] !border-[2px] !border-surface" style={{ top: '50%', width: `${handleSize * 0.83}px`, height: `${handleSize * 0.83}px` }} />
        </>
      ) : (
        <>
          <Handle type="source" position={Position.Bottom} className="!bg-[hsl(var(--card))] !border-[2px] !border-[hsl(var(--brand-500))]" style={{ width: `${handleSize}px`, height: `${handleSize}px` }} />
          <Handle type="source" position={Position.Right} id="error" className="!bg-[hsl(var(--warning-500))] !border-[2px] !border-surface" style={{ top: '50%', width: `${handleSize * 0.83}px`, height: `${handleSize * 0.83}px` }} />
        </>
      )}
    </div>
  )
}

export const ModuleNode = memo(ModuleNodeComponent)
