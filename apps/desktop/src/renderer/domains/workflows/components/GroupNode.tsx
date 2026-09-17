// Source: WebRPA@5ccb900e, components/workflow/GroupNode.tsx; see SOURCE.md for license and adaptation boundaries.
import { memo, useState, useCallback } from 'react'
import { Handle, Position, NodeResizer, type NodeProps } from '@xyflow/react'
import { MessageSquare, GripVertical, Workflow, Magnet } from 'lucide-react'
import { useWorkflowStore, type NodeData } from '../editor-store'

export interface GroupNodeData {
  label: string
  moduleType: 'group'
  color?: string
  isSubflow?: boolean  // 是否为子流程定义
  subflowName?: string // 子流程名称（用于调用）
  width?: number       // 分组宽度（用于后端计算）
  height?: number      // 分组高度（用于后端计算）
}

const COLORS = [
  { name: '蓝色', value: '#3b82f6', bg: 'rgba(59, 130, 246, 0.1)', border: 'rgba(59, 130, 246, 0.3)' },
  { name: '绿色', value: '#22c55e', bg: 'rgba(34, 197, 94, 0.1)', border: 'rgba(34, 197, 94, 0.3)' },
  { name: '紫色', value: '#a855f7', bg: 'rgba(168, 85, 247, 0.1)', border: 'rgba(168, 85, 247, 0.3)' },
  { name: '橙色', value: '#f97316', bg: 'rgba(249, 115, 22, 0.1)', border: 'rgba(249, 115, 22, 0.3)' },
  { name: '红色', value: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)', border: 'rgba(239, 68, 68, 0.3)' },
  { name: '青色', value: '#06b6d4', bg: 'rgba(6, 182, 212, 0.1)', border: 'rgba(6, 182, 212, 0.3)' },
  { name: '粉色', value: '#ec4899', bg: 'rgba(236, 72, 153, 0.1)', border: 'rgba(236, 72, 153, 0.3)' },
  { name: '灰色', value: '#6b7280', bg: 'rgba(107, 114, 128, 0.1)', border: 'rgba(107, 114, 128, 0.3)' },
]

// 子流程专用颜色
const SUBFLOW_COLOR = { 
  name: '子流程', 
  value: '#10b981', 
  bg: 'rgba(16, 185, 129, 0.15)', 
  border: 'rgba(16, 185, 129, 0.4)' 
}

export const GroupNode = memo(({ id, data, selected }: NodeProps) => {
  const nodeData = data as unknown as GroupNodeData
  const nodes = useWorkflowStore((state) => state.nodes)
  const updateNodeData = useWorkflowStore((state) => state.updateNodeData)
  const updateNodesData = useWorkflowStore((state) => state.updateNodesData)
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(nodeData.label || '')
  
  const isSubflow = nodeData.isSubflow === true
  const colorConfig = isSubflow ? SUBFLOW_COLOR : (COLORS.find(c => c.value === nodeData.color) || COLORS[0])

  const handleDoubleClick = useCallback(() => {
    setIsEditing(true)
    setEditValue(nodeData.label || '')
  }, [nodeData.label])

  const handleBlur = useCallback(() => {
    setIsEditing(false)
    const oldName = nodeData.subflowName || nodeData.label || ''
    const newName = editValue
    
    const patches: { nodeId: string; data: Partial<NodeData> }[] = [{
      nodeId: id,
      data: { label: editValue, ...(isSubflow ? { subflowName: editValue } : {}) },
    }]
    if (isSubflow && oldName !== newName) {
      for (const node of nodes) {
        if (node.data.moduleType === 'subflow' &&
            (node.data.subflowGroupId === id || (oldName && node.data.subflowName === oldName))) {
          patches.push({ nodeId: node.id, data: { subflowName: newName } })
        }
      }
    }
    updateNodesData(patches)
  }, [editValue, nodeData, isSubflow, nodes, updateNodesData, id])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleBlur()
    }
    if (e.key === 'Escape') {
      setIsEditing(false)
      setEditValue(nodeData.label || '')
    }
  }, [handleBlur, nodeData.label])

  // 处理尺寸变化结束，将宽高保存到 data 中
  const handleResizeEnd = useCallback((_event: unknown, params: { width: number; height: number }) => {
    updateNodeData(id, { width: params.width, height: params.height })
  }, [id, updateNodeData])

  // 吸附开关：默认开启（adhesion !== false）
  const adhesionEnabled = (nodeData as any).adhesion !== false
  const toggleAdhesion = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    updateNodeData(id, { adhesion: !adhesionEnabled })
  }, [adhesionEnabled, id, updateNodeData])

  return (
    <>
      <NodeResizer
        minWidth={200}
        minHeight={150}
        isVisible={selected}
        lineClassName={isSubflow ? "!border-[hsl(var(--success-500))]" : "!border-[hsl(var(--brand-500))]"}
        handleClassName="!w-3 !h-3 !bg-[hsl(var(--brand-500))] !border-2 !border-white !rounded-full"
        onResizeEnd={handleResizeEnd}
      />

      <div
        className="w-full h-full rounded-card relative transition-shadow duration-200"
        style={{
          backgroundColor: colorConfig.bg,
          border: `2px ${isSubflow ? 'solid' : 'dashed'} ${selected ? colorConfig.value : colorConfig.border}`,
          boxShadow: selected
            ? `0 8px 24px -8px ${colorConfig.value}40, 0 4px 8px -4px ${colorConfig.value}25`
            : 'none',
        }}
      >
        {/* 标题栏 */}
        <div
          className="absolute -top-8 left-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-control text-white text-[12px] font-semibold cursor-move shadow-soft transition-all duration-200 hover:shadow-pop"
          style={{
            background: `linear-gradient(135deg, ${colorConfig.value}, ${colorConfig.value}dd)`,
            border: `1px solid ${colorConfig.value}`,
          }}
          onDoubleClick={handleDoubleClick}
        >
          <GripVertical className="w-3 h-3 opacity-70" />
          {isSubflow ? (
            <Workflow className="w-3.5 h-3.5" strokeWidth={2.4} />
          ) : (
            <MessageSquare className="w-3.5 h-3.5" strokeWidth={2.4} />
          )}
          {isEditing ? (
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
              className="bg-white/20 border border-white/30 rounded outline-none text-white text-[12px] w-32 px-1.5 placeholder:text-white/60"
              autoFocus
              onClick={(e) => e.stopPropagation()}
              placeholder={isSubflow ? "子流程名称" : "输入备注"}
            />
          ) : (
            <span className="tracking-tight">
              {nodeData.label || (isSubflow ? '未命名子流程' : '分组')}
            </span>
          )}
          {/* 吸附开关：仅普通分组显示 */}
          {!isSubflow && (
            <button
              onClick={toggleAdhesion}
              onDoubleClick={(e) => e.stopPropagation()}
              title={adhesionEnabled ? '吸附已开启：拖动分组会带动组内模块（点击关闭）' : '吸附已关闭：拖动分组不影响组内模块（点击开启）'}
              className={
                'relative ml-1 flex items-center justify-center w-5 h-5 rounded transition-colors ' +
                (adhesionEnabled
                  ? 'bg-white/25 hover:bg-white/40'
                  : 'bg-white/5 hover:bg-white/20 opacity-60')
              }
            >
              <Magnet className="w-3 h-3" strokeWidth={2.4} />
              {!adhesionEnabled && (
                <span className="absolute w-4 h-[1.5px] bg-white rotate-45 rounded-full" />
              )}
            </button>
          )}
        </div>

        {/* 子流程标识 */}
        {isSubflow && (
          <div className="absolute top-2 right-2 px-2 py-0.5 rounded-control bg-[hsl(var(--success-500))] text-white text-[9.5px] font-bold uppercase tracking-wider shadow-success-glow">
            子流程
          </div>
        )}
      </div>

      <Handle type="target" position={Position.Top} className="!opacity-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-0 !h-0" />
    </>
  )
})

GroupNode.displayName = 'GroupNode'
