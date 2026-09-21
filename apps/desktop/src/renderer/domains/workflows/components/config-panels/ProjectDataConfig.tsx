import { useEffect, useState } from 'react'
import type { components } from '../../../../shared/api/generated'
import { apiRequest } from '../../api'
import type { NodeData } from '../../editor-store'
import { VariableInput } from '../controls/variable-input'
import { SelectNative as Select } from '../controls/select-native'
import { Label } from '../controls/label'

type Schema = components['schemas']
const operations = { inputs: '读取本次任务输入', readRecord: '读取记录', queryRecords: '查询记录', queryTableSchema: '查询表结构', createRecord: '创建记录', updateRecord: '更新记录', deleteRecord: '删除记录', setRecordStatus: '设置记录状态', addField: '添加字段', ensureField: '确保字段存在', modifyField: '修改字段', previewFieldChange: '预览字段变更' }

export function ProjectDataConfig({ data, onChange }: { data: NodeData; onChange(key: string, value: unknown): void }) {
  const operation = String(data.operation ?? 'inputs')
  const projectId = String(data.bindingProjectId ?? '')
  const grant = data.tableGrant as { tableId: string; datasetGeneration: string; fieldIds: string[] } | undefined
  const tableId = grant?.tableId ?? ''
  const [projects, setProjects] = useState<Schema['ProjectPage']['items']>([])
  const [tables, setTables] = useState<Schema['DataTablePage']['items']>([])
  const [fields, setFields] = useState<Schema['DataFieldDirectory']['items']>([])
  const [projectPage, setProjectPage] = useState(1)
  const [tablePage, setTablePage] = useState(1)
  const [projectTotal, setProjectTotal] = useState(0)
  const [tableTotal, setTableTotal] = useState(0)
  const [error, setError] = useState('')
  const [revision, refresh] = useState(0)
  useEffect(() => {
    const reload = () => { setProjects([]); setTables([]); setFields([]); refresh(value => value + 1) }
    window.addEventListener('studio:transport-changed', reload)
    window.addEventListener('studio:connection-restored', reload)
    return () => { window.removeEventListener('studio:transport-changed', reload); window.removeEventListener('studio:connection-restored', reload) }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setError('')
      const result = await apiRequest<Schema['ProjectPage']>(`/v1/projects?pageSize=100&lifecycleState=active&page=${projectPage}`, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (!result.success || !result.data) { setError('项目列表读取失败，请重试'); return }
      setProjects(result.data.items); setProjectTotal(result.data.total)
      if (!projectId) { setTables([]); setFields([]); return }
      const tableResult = await apiRequest<Schema['DataTablePage']>(`/v1/projects/${encodeURIComponent(projectId)}/tables?pageSize=100&page=${tablePage}`, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (!tableResult.success || !tableResult.data) { setError('数据表读取失败，请重试'); return }
      setTables(tableResult.data.items); setTableTotal(tableResult.data.total)
      if (!tableId) { setFields([]); return }
      const fieldResult = await apiRequest<Schema['DataFieldDirectory']>(`/v1/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(tableId)}/fields`, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (!fieldResult.success || !fieldResult.data) { setError('字段读取失败，请重试'); return }
      setFields(fieldResult.data.items)
    }
    void load()
    return () => controller.abort()
  }, [projectId, tableId, revision, projectPage, tablePage])
  function bind(table: Schema['DataTableView'], op = operation) {
    onChange('tableGrant', { tableId: table.tableId, datasetGeneration: table.datasetGeneration, operations: [op === 'previewFieldChange' ? 'modifyField' : op], fieldIds: [], readPurposes: op === 'queryTableSchema' ? [] : ['condition', 'derivedWrite'] })
    onChange('argumentsValid', true)
    onChange('arguments', initialArguments(op, table))
  }
  return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">从项目自动化批次运行。使用任务的输入快照和数据权限，表发生重建时需要重新选择。</p>
    <Label htmlFor="project-data-operation">操作</Label>
    <Select id="project-data-operation" value={operation} onChange={event => {
      const next = event.target.value
      onChange('operation', next); onChange('argumentsValid', true); onChange('arguments', {}); onChange('tableGrant', undefined)
    }}>{Object.entries(operations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>
    {operation !== 'inputs' && <>
      <Label htmlFor="project-data-project">所属项目</Label>
      <Select id="project-data-project" value={projectId} onChange={event => { setTablePage(1); onChange('bindingProjectId', event.target.value); onChange('tableGrant', undefined); onChange('arguments', {}) }}>
        <option value="">选择项目</option>{projects.map(project => <option key={project.projectId} value={project.projectId}>{project.name}</option>)}
      </Select>
      <div className="flex gap-2"><button type="button" disabled={projectPage === 1} onClick={() => setProjectPage(value => value - 1)}>上一页项目</button><span>第 {projectPage} 页</span><button type="button" disabled={projectPage * 100 >= projectTotal} onClick={() => setProjectPage(value => value + 1)}>下一页项目</button></div>
      <Label htmlFor="project-data-table">授权数据表</Label>
      <Select id="project-data-table" value={tableId} onChange={event => { const table = tables.find(item => item.tableId === event.target.value); if (table) bind(table) }}>
        <option value="">选择数据表</option>{tables.map(table => <option key={table.tableId} value={table.tableId}>{table.name}</option>)}
      </Select>
      <div className="flex gap-2"><button type="button" disabled={tablePage === 1} onClick={() => setTablePage(value => value - 1)}>上一页数据表</button><span>第 {tablePage} 页</span><button type="button" disabled={tablePage * 100 >= tableTotal} onClick={() => setTablePage(value => value + 1)}>下一页数据表</button></div>
      {fields.length > 0 && <fieldset><legend>允许访问的字段</legend>{fields.map(field => <label className="flex gap-2" key={field.ref.fieldId}>
        <input type="checkbox" checked={grant?.fieldIds.includes(field.ref.fieldId) ?? false} onChange={event => {
          const fieldIds = event.target.checked ? [...(grant?.fieldIds ?? []), field.ref.fieldId] : (grant?.fieldIds ?? []).filter(id => id !== field.ref.fieldId)
          onChange('tableGrant', { ...grant, operations: [operation], readPurposes: operation === 'queryTableSchema' ? [] : ['condition', 'derivedWrite'], fieldIds })
          if (operation === 'readRecord' || operation === 'queryRecords' || operation === 'queryTableSchema') onChange('arguments', { ...(data.arguments as Record<string, unknown>), fieldIds })
        }} />{field.name} <code className="break-all text-xs">{field.ref.fieldId}</code>
      </label>)}</fieldset>}
      <Arguments key={JSON.stringify(data.arguments)} value={data.arguments} onChange={value => { onChange('argumentsValid', true); onChange('arguments', value) }} onInvalid={() => onChange('argumentsValid', false)} />
    </>}
    {error && <p role="alert">{error} <button type="button" onClick={() => refresh(value => value + 1)}>重试</button></p>}
    <Label htmlFor="project-data-result">结果变量</Label>
    <VariableInput id="project-data-result" value={String(data.variableName ?? '')} onChange={value => onChange('variableName', value)} placeholder="例如 saved_record" />
  </div>
}

function Arguments({ value, onChange, onInvalid }: { value: unknown; onChange(value: Record<string, unknown>): void; onInvalid(): void }) {
  const [text, setText] = useState(JSON.stringify(value ?? {}, null, 2))
  const [error, setError] = useState('')
  return <div><Label htmlFor="project-data-arguments">操作参数（JSON，值可引用变量）</Label>
    <textarea id="project-data-arguments" className="min-h-40 w-full font-mono text-xs" value={text} aria-invalid={Boolean(error)} onChange={event => setText(event.target.value)} onBlur={() => {
      try {
        const parsed: unknown = JSON.parse(text)
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('object')
        if (['projectId', 'operationId', 'executionGeneration'].some(key => key in parsed)) throw new Error('authority')
        setError(''); onChange(parsed as Record<string, unknown>)
      } catch { onInvalid(); setError('请输入 JSON 对象；任务身份由系统确定，不能在参数中覆盖。') }
    }} />{error && <p role="alert">{error}</p>}
  </div>
}

function initialArguments(operation: string, table: Schema['DataTableView']): Record<string, unknown> {
  const identity = { tableId: table.tableId, datasetGeneration: table.datasetGeneration }
  const recordRef = "{record['ref']}"
  const expectedContentRevision = "{record['contentRevision']}"
  switch (operation) {
    case 'createRecord': return { ...identity, values: {} }
    case 'queryTableSchema': return { ...identity, fieldIds: [] }
    case 'queryRecords': return { ...identity, fieldIds: [], readPurpose: 'condition', filter: null, orderBy: [], cursor: null, limit: 100 }
    case 'readRecord': return { recordRef, fieldIds: [], readPurpose: 'condition' }
    case 'updateRecord': return { recordRef, changes: {}, expectedContentRevision }
    case 'deleteRecord': return { recordRef, expectedContentRevision, expectedStatusRevision: "{record['statusRevision']}", expectedLinkRevision: "{record['linkRevision']}" }
    case 'setRecordStatus': return { recordRef, statusId: null, expectedStatusRevision: "{record['statusRevision']}" }
    default: return { ...identity, fieldId: operation === 'addField' || operation === 'ensureField' ? crypto.randomUUID() : '', definition: { key: '', name: '', type: 'string', required: false, validation: {} }, ...(operation === 'previewFieldChange' ? {} : { expectedTableRevision: table.tableRevision }), ...(operation === 'addField' || operation === 'ensureField' ? { hasDefault: false, default: null } : operation === 'modifyField' ? { expectedFieldRevision: 1, impactRevision: "{preview['impactRevision']}" } : {}) }
  }
}
