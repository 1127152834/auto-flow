import { useProjectInputs, inputReference } from '../../project-inputs'
import { useEffect, useRef, useState } from 'react'
import type { components } from '../../../../shared/api/generated'
import { apiRequest } from '../../api'
import type { NodeData } from '../../editor-store'
import { VariableInput } from '../controls/variable-input'
import { SelectNative as Select } from '../controls/select-native'
import { Label } from '../controls/label'
import { SchemaImpactDrawer } from '../../../project-data/components/SchemaImpactDrawer'

type Schema = components['schemas']
const operations = { inputs: '读取本次任务输入', readRecord: '读取记录', queryRecords: '查询记录', queryTableSchema: '查询表结构', createRecord: '创建记录', updateRecord: '更新记录', deleteRecord: '删除记录', setRecordStatus: '设置记录状态', addField: '添加字段', ensureField: '确保字段存在', modifyField: '修改字段', previewFieldChange: '预览字段变更', previewFieldDeletion: '预览字段删除', deleteField: '删除字段' }

const grantOperation = (operation: string) => ({ previewFieldChange: 'modifyField', previewFieldDeletion: 'deleteField' })[operation] ?? operation
const readPurposes = (operation: string) => ['queryTableSchema', 'deleteField', 'previewFieldDeletion'].includes(operation) ? [] : ['condition', 'derivedWrite']

export function ProjectDataConfig({ data, onChange }: { data: NodeData; onChange(key: string, value: unknown): void }) {
  const automation = useProjectInputs(state => state.automation)
  const operation = String(data.operation ?? 'inputs')
  const currentInput = automation?.inputPlan.inputs.find(input => input.inputId === data.currentInputId)
  const projectId = String(data.bindingProjectId ?? '')
  const grant = data.tableGrant as { tableId: string; datasetGeneration: string; fieldIds: string[] } | undefined
  const tableId = grant?.tableId ?? ''
  const [projects, setProjects] = useState<Schema['ProjectPage']['items']>([])
  const [tables, setTables] = useState<Schema['DataTablePage']['items']>([])
  const [fields, setFields] = useState<Schema['DataFieldDirectory']['items']>([])
  const [statuses, setStatuses] = useState<Schema['DataStatusView'][]>([])
  const [projectPage, setProjectPage] = useState(1)
  const [tablePage, setTablePage] = useState(1)
  const [projectTotal, setProjectTotal] = useState(0)
  const [tableTotal, setTableTotal] = useState(0)
  const [error, setError] = useState('')
  const [revision, refresh] = useState(0)
  const [deletionImpact, setDeletionImpact] = useState<Schema['DataSchemaImpact'] | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewBusy, setPreviewBusy] = useState(false)
  const previewRequest = useRef<AbortController | null>(null)
  const argumentsValue = data.arguments as Record<string, unknown> | undefined
  const fieldId = String(argumentsValue?.fieldId ?? '')
  const deleting = operation === 'deleteField' || operation === 'previewFieldDeletion'
  const selectedField = fields.find(field => field.ref.fieldId === fieldId)
  useEffect(() => {
    previewRequest.current?.abort(); setPreviewOpen(false); setDeletionImpact(null); setPreviewBusy(false)
    return () => previewRequest.current?.abort()
  }, [projectId, tableId, fieldId, operation, revision])
  async function previewDeletion() {
    const table = tables.find(item => item.tableId === tableId)
    if (!table || !selectedField) return
    previewRequest.current?.abort()
    const controller = new AbortController(); previewRequest.current = controller
    setPreviewBusy(true); setError('')
    const candidate: Schema['DataSchemaCandidate'] = { datasetGeneration: table.datasetGeneration, expectedTableRevision: table.tableRevision,
      removedFieldIds: [fieldId], fields: fields.filter(field => field.ref.fieldId !== fieldId).map(field => ({ kind: 'existing', fieldId: field.ref.fieldId, expectedFieldRevision: field.fieldRevision,
        definition: { key: field.key, name: field.name, type: field.type, required: field.required, validation: field.validation } })) }
    const result = await apiRequest<Schema['DataSchemaImpact']>(`/v1/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(tableId)}/schema/preview`, { method: 'POST', body: JSON.stringify(candidate), signal: controller.signal })
    if (controller.signal.aborted) return
    setPreviewBusy(false)
    if (!result.success || !result.data) { setError('删除影响读取失败，请刷新后重试'); return }
    setDeletionImpact(result.data); setPreviewOpen(true)
  }
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
      const statusResult = await apiRequest<Schema['DataStatusDirectory']>(`/v1/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(tableId)}/statuses`, { signal: controller.signal })
      if (controller.signal.aborted) return
      if (!statusResult.success || !statusResult.data) { setStatuses([]); setError('业务状态读取失败，请重试'); return }
      setStatuses(statusResult.data.items)
    }
    void load()
    return () => controller.abort()
  }, [projectId, tableId, revision, projectPage, tablePage])
  function bind(table: Schema['DataTableView'], op = operation) {
    onChange('currentInputId', undefined)
    onChange('tableGrant', { tableId: table.tableId, datasetGeneration: table.datasetGeneration, operations: [grantOperation(op)], fieldIds: [], readPurposes: readPurposes(op) })
    onChange('argumentsValid', true)
    onChange('arguments', initialArguments(op, table))
  }
  function selectInput(inputId: string) {
    const input = automation?.inputPlan.inputs.find(item => item.inputId === inputId)
    if (!input || !automation) return
    const ids = input.fieldBindings.map(binding => binding.fieldRef.fieldId)
    const ref = inputReference(inputId)
    onChange('currentInputId', inputId)
    onChange('bindingProjectId', automation.projectId)
    onChange('tableGrant', { tableId: input.tableId, datasetGeneration: input.datasetGeneration, operations: [operation], fieldIds: ids, readPurposes: readPurposes(operation) })
    onChange('argumentsValid', true)
    onChange('arguments', { recordRef: `{${ref}['recordRef']}`, ...(operation === 'readRecord' ? { fieldIds: ids, readPurpose: 'condition' } : operation === 'setRecordStatus' ? { expectedStatusRevision: `{${ref}['statusRevision']}`, statusId: null } : { expectedContentRevision: `{${ref}['contentRevision']}`, changes: {} }) })
  }
  return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">从项目自动化批次运行。使用任务的输入快照和数据权限，表发生重建时需要重新选择。</p>
    <Label htmlFor="project-data-operation">操作</Label>
    <Select id="project-data-operation" value={operation} onChange={event => {
      const next = event.target.value
      onChange('currentInputId', undefined); onChange('operation', next); if (next === 'previewFieldDeletion') onChange('variableName', 'field_deletion_preview'); onChange('argumentsValid', true); onChange('arguments', {}); onChange('tableGrant', undefined)
    }}>{Object.entries(operations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>
    {automation && ['readRecord', 'updateRecord', 'setRecordStatus'].includes(operation) && <><Label htmlFor="project-current-input">当前输入对象</Label><Select id="project-current-input" value={String(data.currentInputId ?? '')} onChange={event => selectInput(event.target.value)}><option value="">选择本次任务的输入对象</option>{automation.inputPlan.inputs.map(input => <option key={input.inputId} value={input.inputId}>{input.alias}</option>)}</Select></>}
    {currentInput && operation === 'setRecordStatus' && <><Label htmlFor="project-input-status">保存业务状态</Label><Select id="project-input-status" value={String(argumentsValue?.statusId ?? '')} onChange={event => onChange('arguments', { ...argumentsValue, statusId: event.target.value || null })}><option value="">未设置</option>{statuses.map(status => <option key={status.statusId} value={status.statusId}>{status.name}</option>)}</Select></>}
    {operation !== 'inputs' && <>
      <Label htmlFor="project-data-project">所属项目</Label>
      <Select id="project-data-project" value={projectId} onChange={event => { setTablePage(1); onChange('currentInputId', undefined); onChange('bindingProjectId', event.target.value); onChange('tableGrant', undefined); onChange('arguments', {}) }}>
        <option value="">选择项目</option>{projects.map(project => <option key={project.projectId} value={project.projectId}>{project.name}</option>)}
      </Select>
      <div className="flex gap-2"><button type="button" disabled={projectPage === 1} onClick={() => setProjectPage(value => value - 1)}>上一页项目</button><span>第 {projectPage} 页</span><button type="button" disabled={projectPage * 100 >= projectTotal} onClick={() => setProjectPage(value => value + 1)}>下一页项目</button></div>
      <Label htmlFor="project-data-table">授权数据表</Label>
      <Select id="project-data-table" value={tableId} onChange={event => { const table = tables.find(item => item.tableId === event.target.value); if (table) bind(table) }}>
        <option value="">选择数据表</option>{tables.map(table => <option key={table.tableId} value={table.tableId}>{table.name}</option>)}
      </Select>
      <div className="flex gap-2"><button type="button" disabled={tablePage === 1} onClick={() => setTablePage(value => value - 1)}>上一页数据表</button><span>第 {tablePage} 页</span><button type="button" disabled={tablePage * 100 >= tableTotal} onClick={() => setTablePage(value => value + 1)}>下一页数据表</button></div>
      {!deleting && fields.length > 0 && <fieldset><legend>允许访问的字段</legend>{fields.map(field => <label className="flex gap-2" key={field.ref.fieldId}>
        <input type="checkbox" checked={grant?.fieldIds.includes(field.ref.fieldId) ?? false} onChange={event => {
          const fieldIds = event.target.checked ? [...(grant?.fieldIds ?? []), field.ref.fieldId] : (grant?.fieldIds ?? []).filter(id => id !== field.ref.fieldId)
          onChange('tableGrant', { ...grant, operations: [grantOperation(operation)], readPurposes: readPurposes(operation), fieldIds })
          if (operation === 'readRecord' || operation === 'queryRecords' || operation === 'queryTableSchema') onChange('arguments', { ...(data.arguments as Record<string, unknown>), fieldIds })
        }} />{field.name} <code className="break-all text-xs">{field.ref.fieldId}</code>
      </label>)}</fieldset>}
      {deleting && <>
        <Label htmlFor="project-data-delete-field">删除字段</Label>
        <Select id="project-data-delete-field" value={fieldId} onChange={event => {
          onChange('arguments', { ...argumentsValue, fieldId: event.target.value })
          onChange('tableGrant', { ...grant, operations: ['deleteField'], fieldIds: operation === 'previewFieldDeletion' ? [event.target.value] : [], readPurposes: [] })
        }}><option value="">选择字段</option>{fields.map(field => <option key={field.ref.fieldId} value={field.ref.fieldId}>{field.name}</option>)}</Select>
        <p className="text-sm text-muted-foreground">仅删除本地字段及对应值。运行时使用“预览字段删除”的结果，提交前再次检查引用。</p>
        <button type="button" disabled={previewBusy || !selectedField || !tables.some(table => table.tableId === tableId)} onClick={() => void previewDeletion()}>{previewBusy ? '正在检查…' : '预览删除影响'}</button>
        <SchemaImpactDrawer open={previewOpen} tableName={tables.find(table => table.tableId === tableId)?.name ?? '数据表'} sourceLabel="不删除远端来源列" confirmLabel="确认删除目标"
          changes={selectedField ? [{ id: fieldId, name: selectedField.name, key: selectedField.key, summary: '删除本地字段及对应值' }] : []}
          impact={deletionImpact} onOpenChange={setPreviewOpen} onConfirm={() => {
            onChange('tableGrant', { ...grant, operations: ['deleteField'], fieldIds: [fieldId], readPurposes: [] })
            setPreviewOpen(false)
          }} />
      </>}
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
    case 'previewFieldDeletion': return { ...identity, fieldId: '' }
    case 'deleteField': return { ...identity, fieldId: '', expectedTableRevision: "{field_deletion_preview['tableRevision']}", impactRevision: "{field_deletion_preview['impactRevision']}" }
    case 'queryTableSchema': return { ...identity, fieldIds: [] }
    case 'queryRecords': return { ...identity, fieldIds: [], readPurpose: 'condition', filter: null, orderBy: [], cursor: null, limit: 100 }
    case 'readRecord': return { recordRef, fieldIds: [], readPurpose: 'condition' }
    case 'updateRecord': return { recordRef, changes: {}, expectedContentRevision }
    case 'deleteRecord': return { recordRef, expectedContentRevision, expectedStatusRevision: "{record['statusRevision']}", expectedLinkRevision: "{record['linkRevision']}" }
    case 'setRecordStatus': return { recordRef, statusId: null, expectedStatusRevision: "{record['statusRevision']}" }
    default: return { ...identity, fieldId: operation === 'addField' || operation === 'ensureField' ? crypto.randomUUID() : '', definition: { key: '', name: '', type: 'string', required: false, validation: {} }, ...(operation === 'previewFieldChange' ? {} : { expectedTableRevision: table.tableRevision }), ...(operation === 'addField' || operation === 'ensureField' ? { hasDefault: false, default: null } : operation === 'modifyField' ? { expectedFieldRevision: 1, impactRevision: "{preview['impactRevision']}" } : {}) }
  }
}
