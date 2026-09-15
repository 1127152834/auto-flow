// Source: WebRPA@5ccb900e, components/workflow/SubflowHeaderNode.tsx; see SOURCE.md for license and adaptation boundaries.
import { memo, useState, useCallback } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Workflow, GripVertical, ChevronDown, ChevronUp } from 'lucide-react'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
import { useWorkflowStore, type NodeData } from '../editor-store'
import { useConfirm } from './controls/confirm-dialog'

export interface SubflowHeaderNodeData {
  label: string
  moduleType: 'subflow_header'
  subflowName?: string // 子流程名称（用于调用）
  originalGroupId?: string // 原分组ID（用于转换时的引用）
  collapsed?: boolean // 是否折叠
}

export const SubflowHeaderNode = memo(({ id, data, selected }: NodeProps) => {
  const nodeData = data as unknown as SubflowHeaderNodeData
  const nodes = useWorkflowStore((state) => state.nodes)
  const edges = useWorkflowStore((state) => state.edges)
  const onNodesChange = useWorkflowStore((state) => state.onNodesChange)
  const updateNodesData = useWorkflowStore((state) => state.updateNodesData)
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState(nodeData.label || '')
  const { alert: alertDialog, ConfirmDialog } = useConfirm()
  
  const isCollapsed = nodeData.collapsed === true
  
  // 获取全局配置的连接点尺寸
  const handleSize = useGlobalConfigStore((state) => state.config.display?.handleSize || 12)

  // 切换折叠状态
  const toggleCollapse = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    
    const currentNode = nodes.find(n => n.id === id)
    if (!currentNode) return
    
    const newCollapsed = !isCollapsed
    
    // 找出从当前节点出发的所有连接的目标节点
    const directTargets = edges
      .filter(e => e.source === id)
      .map(e => e.target)
    
    if (directTargets.length === 0) return
    
    // 递归查找所有子节点（通过边连接的所有下游节点）
    const findAllDescendants = (nodeId: string, visited = new Set<string>()): Set<string> => {
      if (visited.has(nodeId)) return visited
      visited.add(nodeId)
      
      const children = edges
        .filter(e => e.source === nodeId)
        .map(e => e.target)
      
      children.forEach(childId => {
        if (!visited.has(childId)) {
          findAllDescendants(childId, visited)
        }
      })
      
      return visited
    }
    
    // 获取所有下游节点
    const allDescendants = new Set<string>()
    directTargets.forEach(targetId => {
      findAllDescendants(targetId, allDescendants)
    })
    
    const nextNodes = nodes.map((node) => {
      if (node.id === id) return { ...node, data: { ...node.data, collapsed: newCollapsed } }
      if (allDescendants.has(node.id)) return { ...node, hidden: newCollapsed }
      return node
    })
    onNodesChange(nextNodes.map((node) => ({ type: 'replace' as const, id: node.id, item: node })))
  }, [id, isCollapsed, nodes, edges, onNodesChange])

  const handleDoubleClick = useCallback(() => {
    setIsEditing(true)
    setEditValue(nodeData.label || '')
  }, [nodeData.label])

  const handleBlur = useCallback(() => {
    setIsEditing(false)
    const oldName = nodeData.subflowName || nodeData.label || ''
    const newName = editValue
    
    // 检查是否有重名
    if (newName) {
      const duplicates = nodes.filter(n => {
        if (n.id === id) return false
        if (n.type === 'groupNode' && n.data.isSubflow && n.data.subflowName === newName) return true
        if (n.type === 'subflowHeaderNode' && n.data.subflowName === newName) return true
        return false
      })
      
      if (duplicates.length > 0) {
        alertDialog(`已存在名为「${newName}」的子流程！\n\n这会导致调用时无法确定执行哪一个，请使用唯一的名称。`, { title: '名称重复' })
        setEditValue(oldName)
        return
      }
    }
    
    const patches: { nodeId: string; data: Partial<NodeData> }[] = [
      { nodeId: id, data: { label: editValue, subflowName: editValue } },
    ]
    if (oldName !== newName) {
      for (const node of nodes) {
        if (node.data.moduleType === 'subflow' &&
            (node.data.subflowGroupId === id || (oldName && node.data.subflowName === oldName))) {
          patches.push({ nodeId: node.id, data: { subflowName: newName } })
        }
      }
    }
    updateNodesData(patches)
  }, [editValue, nodeData, id, nodes, updateNodesData, alertDialog])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleBlur()
    }
    if (e.key === 'Escape') {
      setIsEditing(false)
      setEditValue(nodeData.label || '')
    }
  }, [handleBlur, nodeData.label])

  return (
    <>
    <div
      className={`relative px-4 py-3 rounded-lg border-2 transition-all cursor-move ${
        selected 
          ? 'border-emerald-500 shadow-lg shadow-emerald-500/20' 
          : 'border-emerald-400 shadow-md'
      }`}
      style={{
        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.1) 100%)',
        minWidth: '280px',
      }}
    >
      {/* 顶部装饰线 */}
      <div className="bg-[hsl(var(--card))] absolute top-0 left-0 right-0 h-1 rounded-t-lg" />
      
      {/* 折叠按钮 - 右上角 */}
      <button
        onClick={toggleCollapse}
        className="absolute top-2 right-2 z-20 p-1 rounded bg-emerald-600 hover:bg-emerald-700 text-white transition-all shadow-md"
        title={isCollapsed ? "展开子流程" : "折叠子流程"}
      >
        {isCollapsed ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronUp className="w-3.5 h-3.5" />
        )}
      </button>
      
      {/* 主体内容 */}
      <div className="flex items-center gap-3">
        {/* 图标 */}
        <div className="bg-[hsl(var(--card))] flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center shadow-md">
          <Workflow className="w-5 h-5 text-white" />
        </div>
        
        {/* 标题区域 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <GripVertical className="w-3 h-3 text-emerald-600 opacity-70" />
            <span className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wider">
              子流程定义
            </span>
          </div>
          
          {isEditing ? (
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
              className="w-full bg-white/80 border border-emerald-300 rounded px-2 py-1 text-sm font-semibold text-emerald-900 outline-none focus:ring-2 focus:ring-emerald-500"
              autoFocus
              onClick={(e) => e.stopPropagation()}
              placeholder="子流程名称"
            />
          ) : (
            <div
              className="text-sm font-semibold text-emerald-900 truncate cursor-text"
              onDoubleClick={handleDoubleClick}
            >
              {nodeData.label || '未命名子流程'}
            </div>
          )}
        </div>
      </div>
      
      {/* 底部提示 */}
      {!isCollapsed && (
        <div className="mt-2 pt-2 border-t border-emerald-200/50">
          <p className="text-[10px] text-emerald-700 opacity-80">
            ⬇️ 连接到子流程的第一个模块
          </p>
        </div>
      )}
      
      {/* 连接点 - 只有底部输出，没有顶部输入 */}
      {!isCollapsed && (
        <Handle
          type="source"
          position={Position.Bottom}
          className="!bg-emerald-500 !border-2 !border-white"
          style={{ bottom: -6, width: `${handleSize}px`, height: `${handleSize}px` }}
        />
      )}
    </div>
    <ConfirmDialog />
    </>
  )
})

SubflowHeaderNode.displayName = 'SubflowHeaderNode'
