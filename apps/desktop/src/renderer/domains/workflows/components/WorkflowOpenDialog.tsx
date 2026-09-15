import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Clock, FileJson, FolderOpen, RefreshCw, Search, Trash2, X } from 'lucide-react'
import { workflowApi } from '../api'
import { getStudioTransportRevision } from '../api/transport'
import { useWorkflowStore } from '../editor-store'
import { snapshotKey } from '../lib/snapshotKey'
import { Button } from './controls/button'
import { useConfirm } from './controls/confirm-dialog'
import { DialogPortal } from './controls/dialog-portal'
import { Input } from './controls/input'

interface WorkflowInfo {
  id: string
  name: string
  revision: number
  updatedAt: string
}

interface WorkflowOpenDialogProps {
  beforeReplace: () => Promise<boolean>
  isOpen: boolean
  onClose: () => void
  onOpened: (id: string) => void
  onLog: (level: 'info' | 'success' | 'warning' | 'error', message: string) => void
}

function isWorkflowInfo(value: unknown): value is WorkflowInfo {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const row = value as Record<string, unknown>
  return typeof row.id === 'string' && !!row.id && typeof row.name === 'string'
    && Number.isSafeInteger(row.revision) && Number(row.revision) > 0
    && typeof row.updatedAt === 'string'
}

export function WorkflowOpenDialog({ beforeReplace, isOpen, onClose, onOpened, onLog }: WorkflowOpenDialogProps) {
  const importWorkflow = useWorkflowStore(state => state.importWorkflow)
  const [workflows, setWorkflows] = useState<WorkflowInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [listError, setListError] = useState('')
  const [search, setSearch] = useState('')
  const requestSequence = useRef(0)
  const openSequence = useRef(0)
  const { confirm, ConfirmDialog } = useConfirm()

  const load = useCallback(async () => {
    const sequence = ++requestSequence.current
    const connection = getStudioTransportRevision()
    const current = () => sequence === requestSequence.current && connection === getStudioTransportRevision()
    setLoading(true)
    setListError('')
    const result = await workflowApi.list()
    if (!current()) return
    if (!result.success || !Array.isArray(result.data) || !result.data.every(isWorkflowInfo)) {
      setWorkflows([])
      setListError(result.error || '工作流列表返回格式无效')
    } else {
      setWorkflows(result.data)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    if (isOpen) void load()
    else { requestSequence.current++; openSequence.current++ }
  }, [isOpen, load])

  useEffect(() => {
    const invalidate = () => {
      requestSequence.current++
      openSequence.current++
      setWorkflows([])
      setLoading(false)
      setListError('服务连接已变更，请刷新当前工作区的工作流列表')
    }
    window.addEventListener('studio:transport-changed', invalidate)
    return () => window.removeEventListener('studio:transport-changed', invalidate)
  }, [])

  const open = async (workflow: WorkflowInfo) => {
    const sequence = ++openSequence.current
    const connection = getStudioTransportRevision()
    if (!(await beforeReplace()) || sequence !== openSequence.current || connection !== getStudioTransportRevision()) return
    const source = useWorkflowStore.getState()
    const sourceId = source.id
    const sourceSnapshot = snapshotKey(source.exportWorkflow())
    const result = await workflowApi.get(workflow.id)
    if (sequence !== openSequence.current || connection !== getStudioTransportRevision()) return
    const current = useWorkflowStore.getState()
    if (current.id !== sourceId || snapshotKey(current.exportWorkflow()) !== sourceSnapshot) {
      onLog('warning', '加载期间草稿已修改，请重新打开工作流')
      return
    }
    if (!result.success || !result.data || !isWorkflowInfo(result.data)) {
      onLog('error', `打开失败: ${result.error || '工作流响应格式无效'}`)
      return
    }
    if (!importWorkflow(result.data)) {
      onLog('error', '工作流格式无效')
      return
    }
    onOpened(workflow.id)
    onLog('success', `已打开工作流: ${workflow.name}`)
    onClose()
  }

  const remove = async (workflow: WorkflowInfo) => {
    const connection = getStudioTransportRevision()
    if (!(await confirm(`确定要删除工作流 "${workflow.name}" 吗？`, { type: 'warning', title: '删除工作流' })) || connection !== getStudioTransportRevision()) return
    const result = await workflowApi.delete(workflow.id)
    if (connection !== getStudioTransportRevision()) return
    if (!result.success) {
      onLog('error', `删除工作流出错: ${result.error || '服务未返回有效确认'}`)
      return
    }
    onLog('success', `已删除工作流: ${workflow.name}`)
    await load()
  }

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('zh-CN')
    return query ? workflows.filter(item => item.name.toLocaleLowerCase('zh-CN').includes(query)) : workflows
  }, [search, workflows])

  if (!isOpen) return null
  return <DialogPortal>
    <div className="fixed inset-0 bg-[hsl(217_45%_15%_/_0.55)] backdrop-blur-[3px] flex items-center justify-center p-4 animate-fade-in" style={{ zIndex: 2147483646 }}>
      <div className="modern-dialog w-full max-w-2xl animate-scale-in-bounce flex flex-col" style={{ maxHeight: 'calc(100vh - 32px)' }} role="dialog" aria-label="打开工作流">
        <div className="modern-dialog-header">
          <div className="modern-dialog-header-icon modern-dialog-header-icon-warning"><FolderOpen className="w-5 h-5" /></div>
          <div className="flex-1 min-w-0"><h3 className="modern-dialog-title">打开工作流</h3><div className="modern-dialog-subtitle">当前工作区共 {workflows.length} 条流程</div></div>
          <button onClick={onClose} className="p-1.5 rounded-[7px]" title="关闭 (Esc)"><X className="w-4 h-4" /></button>
        </div>
        <div className="px-5 py-3 border-b border-[hsl(var(--border))] flex items-center gap-2">
          <div className="relative flex-1"><Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" /><Input value={search} onChange={event => setSearch(event.target.value)} placeholder="搜索工作流名称..." className="!pl-8" /></div>
          <Button variant="tonal" size="sm" onClick={() => void load()} disabled={loading} loading={loading}>{!loading && <RefreshCw className="w-3.5 h-3.5" />}刷新</Button>
        </div>
        {listError && <p role="alert" className="px-5 py-2 text-sm text-red-600">{listError}</p>}
        <div className="flex-1 overflow-y-auto min-h-[280px] max-h-[480px] p-2">
          {!loading && filtered.length === 0 ? <div className="empty-state"><FileJson className="w-7 h-7" /><div className="empty-state-title">{search ? '未找到匹配工作流' : '当前工作区暂无工作流'}</div></div> : filtered.map(workflow => <div key={workflow.id} className="row-card group !p-3 mb-1" role="button" aria-label={`打开工作流 ${workflow.name}`} tabIndex={0} onClick={() => void open(workflow)} onKeyDown={event => { if (event.key === 'Enter') void open(workflow) }}>
            <div className="icon-chip icon-chip-brand !w-9 !h-9"><FileJson className="w-4 h-4" /></div>
            <div className="flex-1 min-w-0"><div className="text-[13.5px] font-semibold truncate">{workflow.name}</div><div className="text-[11px] text-[hsl(var(--muted-foreground))] flex items-center gap-3"><span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{new Date(workflow.updatedAt).toLocaleString('zh-CN')}</span><span>修订 {workflow.revision}</span></div></div>
            <button onClick={event => { event.stopPropagation(); void remove(workflow) }} className="opacity-0 group-hover:opacity-100 p-1.5" title={`删除工作流 ${workflow.name}`}><Trash2 className="w-3.5 h-3.5" /></button>
          </div>)}
        </div>
        <div className="dialog-footer-bar"><Button variant="secondary" size="sm" onClick={onClose}>关闭</Button></div>
      </div>
      <ConfirmDialog />
    </div>
  </DialogPortal>
}
