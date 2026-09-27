import { useEffect, useId, useState } from 'react'
import type { components } from '../../../../shared/api/generated'
import { apiRequest } from '../../api'
import { getBackendBaseUrl, getStudioOpenContext } from '../../api/config'
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { SelectNative } from '../controls/select-native'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'

type Schema = components['schemas']
type Binding = { tableId: string; datasetGeneration: string; fieldIds: string[] }
const actions = {
  inputs: '领取的输入快照', read: '读取记录', query: '查询记录', update: '修改记录',
  status: '推进记录状态', create: '创建记录', delete: '删除记录',
  addField: '新增字段', ensureField: '确保字段存在', previewField: '预览字段修改', modifyField: '修改字段',
  operation: '查询原操作结果',
}

export function ProjectDataConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  const id = useId()
  const projectId = getStudioOpenContext().projectId
  const origin = projectId ? getBackendBaseUrl() : ''
  const action = String(data.action ?? 'inputs')
  const candidate = data.binding as Partial<Binding> | null | undefined
  const binding = candidate && typeof candidate.tableId === 'string' && typeof candidate.datasetGeneration === 'string'
    && Array.isArray(candidate.fieldIds) && candidate.fieldIds.every(value => typeof value === 'string') ? candidate as Binding : undefined
  const [tables, setTables] = useState<Schema['DataTableView'][]>([])
  const [fields, setFields] = useState<Schema['DataFieldView'][]>([])
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [retry, setRetry] = useState(0)
  const needsBinding = action !== 'inputs' && action !== 'operation'
  useEffect(() => {
    const controller = new AbortController()
    setTables([])
    setError('')
    if (!projectId || !needsBinding) return () => controller.abort()
    void (async () => {
      const items: Schema['DataTableView'][] = []
      for (let page = 1; !controller.signal.aborted; page++) {
        const result = await apiRequest<Schema['DataTablePage']>(`/v1/projects/${encodeURIComponent(projectId)}/tables?page=${page}&pageSize=100&sort=name`, { signal: controller.signal })
        if (controller.signal.aborted || getBackendBaseUrl() !== origin) return
        if (!result.success || !result.data) { setError(result.error ?? '项目数据表读取失败'); return }
        items.push(...result.data.items)
        if (!result.data.items.length || items.length >= result.data.total) break
      }
      if (!controller.signal.aborted) setTables(items)
    })()
    return () => controller.abort()
  }, [projectId, origin, needsBinding, retry])
  useEffect(() => {
    const controller = new AbortController()
    setFields([])
    setFieldError('')
    if (!projectId || !binding?.tableId || !needsBinding) return () => controller.abort()
    void apiRequest<Schema['DataFieldDirectory']>(`/v1/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(binding.tableId)}/fields`, { signal: controller.signal }).then(result => {
      if (controller.signal.aborted || getBackendBaseUrl() !== origin) return
      if (!result.success || !result.data) { setFieldError(result.error ?? '项目字段读取失败'); return }
      if (result.data.items.some(field => field.ref.projectId !== projectId || field.ref.tableId !== binding.tableId || field.ref.datasetGeneration !== binding.datasetGeneration)) {
        setFieldError('数据表版本已变化，请重新选择数据表')
        return
      }
      setFields(result.data.items)
    })
    return () => controller.abort()
  }, [projectId, origin, binding?.tableId, binding?.datasetGeneration, needsBinding, retry])
  return <div className="space-y-4">
    <p className="text-xs text-muted-foreground">保存后从项目自动化任务运行。Studio 直接运行没有任务输入及数据授权。</p>
    {!projectId && <p role="alert">请从项目中打开工作流，项目数据节点需要任务授权。</p>}
    <div className="space-y-2"><Label htmlFor={`${id}-action`}>项目数据操作</Label>
      <SelectNative id={`${id}-action`} value={action} onChange={event => onChange('action', event.target.value)}>
        {Object.entries(actions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </SelectNative>
    </div>
    {needsBinding && <>
      <div className="space-y-2"><Label htmlFor={`${id}-table`}>授权数据表</Label>
        <SelectNative id={`${id}-table`} value={binding?.tableId ?? ''} disabled={!projectId || !!error} onChange={event => {
          const table = tables.find(item => item.tableId === event.target.value)
          if (table) onChange('binding', { tableId: table.tableId, datasetGeneration: table.datasetGeneration, fieldIds: [] })
        }}>
          <option value="">选择当前项目的数据表</option>
          {binding?.tableId && !tables.some(table => table.tableId === binding.tableId) && <option value={binding.tableId}>原数据表待核验</option>}
          {tables.map(table => <option key={table.tableId} value={table.tableId}>{table.name}</option>)}
        </SelectNative>
      </div>
      <fieldset className="space-y-2" disabled={!binding || !!fieldError}><legend className="text-sm">授权字段</legend>
        {fields.map(field => <label key={field.ref.fieldId} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={binding?.fieldIds?.includes(field.ref.fieldId) ?? false} onChange={event => {
            if (!binding) return
            const selected = new Set(binding.fieldIds)
            if (event.target.checked) selected.add(field.ref.fieldId)
            else selected.delete(field.ref.fieldId)
            onChange('binding', { ...binding, fieldIds: [...selected] })
          }} />{field.name}
        </label>)}
      </fieldset>
      <p className="text-xs text-muted-foreground">运行参数必须落在已授权的表和字段范围内。新增字段作用于所选数据表；修改字段必须选中对应字段，或引用本任务创建的字段。</p>
    </>}
    {(error || fieldError) && <div role="alert">{error || fieldError}<button type="button" onClick={() => setRetry(value => value + 1)}>重试读取</button></div>}
    {action !== 'inputs' && <div className="space-y-2"><Label htmlFor={`${id}-arguments`}>操作参数（JSON）</Label>
      <VariableInput id={`${id}-arguments`} multiline rows={8} value={typeof data.arguments === 'string' ? data.arguments : JSON.stringify(data.arguments ?? {}, null, 2)} onChange={value => onChange('arguments', value)} />
      <p className="text-xs text-muted-foreground">支持对象变量与 JSON 模板。记录引用、版本号来自读取结果；对象和数字变量插入 JSON 时不加引号。冲突会终止当前节点，不自动重写。</p>
    </div>}
    <div className="space-y-2"><Label>结果变量</Label><VariableNameInput value={String(data.resultVariable ?? 'project_result')} onChange={value => onChange('resultVariable', value)} /></div>
  </div>
}
