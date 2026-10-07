import { useProjectInputs, inputReference } from '../../project-inputs'
import { useEffect, useState } from 'react'
import type { components } from '../../../../shared/api/generated'
import { apiRequest } from '../../api'
import { getBackendBaseUrl } from '../../api/config'
import type { NodeData } from '../../editor-store'
import { VariableInput } from '../controls/variable-input'
import { SelectNative as Select } from '../controls/select-native'
import { Label } from '../controls/label'
import { ConditionRows, FieldValueRows, ReturnFields } from './ProjectDataForms'

type Schema = components['schemas']
const operations = { inputs: '读取本次任务输入', readRecord: '读取记录', queryRecords: '查询记录', queryTableSchema: '查询表结构', createRecord: '新增记录', updateRecord: '更新当前记录', deleteRecord: '删除记录', setRecordStatus: '设置状态' }
const formOperations = ['createRecord', 'updateRecord', 'setRecordStatus', 'queryRecords']
// Remediation M2 R2-23: runs no longer change table structure; old nodes keep their saved operation.
const structureOperations: Record<string, string> = { addField: '添加字段', ensureField: '确保字段存在', modifyField: '修改字段', previewFieldChange: '预览字段变更', previewFieldDeletion: '预览字段删除', deleteField: '删除字段' }

const readPurposes = (operation: string) => operation === 'queryTableSchema' ? [] : ['condition', 'derivedWrite']

export function ProjectDataConfig({ data, onChange }: { data: NodeData; onChange(key: string, value: unknown): void }) {
  const automation = useProjectInputs(state => state.automation)
  const operation = String(data.operation ?? 'inputs')
  const projectId = String(data.bindingProjectId ?? '')
  const grant = data.tableGrant as { tableId: string; datasetGeneration: string; fieldIds: string[] } | undefined
  const tableId = grant?.tableId ?? ''
  const origin = getBackendBaseUrl()
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
  const argumentsValue = data.arguments as Record<string, unknown> | undefined
  const retired = structureOperations[operation]
  const isForm = formOperations.includes(operation)
  const [showAdvanced, setShowAdvanced] = useState(false)
  function writeForm(patch: Record<string, unknown>, fieldIds: string[]) {
    onChange('argumentsValid', true)
    onChange('arguments', { ...argumentsValue, ...patch })
    if (grant) onChange('tableGrant', { ...grant, operations: [operation], readPurposes: readPurposes(operation), fieldIds })
  }
  const returned = Array.isArray(argumentsValue?.fieldIds) ? argumentsValue.fieldIds.filter((id): id is string => typeof id === 'string') : []
  const filterFieldIds = (filter: Record<string, unknown> | null) => ((filter?.items as { fieldId: string }[] | undefined) ?? []).map(item => item.fieldId)
  useEffect(() => {
    const reload = () => { setProjects([]); setTables([]); setFields([]); setStatuses([]); refresh(value => value + 1) }
    window.addEventListener('studio:transport-changed', reload)
    window.addEventListener('studio:connection-restored', reload)
    return () => { window.removeEventListener('studio:transport-changed', reload); window.removeEventListener('studio:connection-restored', reload) }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    const stale = () => controller.signal.aborted || getBackendBaseUrl() !== origin
    async function load() {
      setError(''); setProjects([]); setTables([]); setFields([]); setStatuses([])
      const result = await apiRequest<Schema['ProjectPage']>(`/v1/projects?pageSize=100&lifecycleState=active&page=${projectPage}`, { signal: controller.signal })
      if (stale()) return
      if (!result.success || !result.data) { setError('项目列表读取失败，请重试'); return }
      setProjects(result.data.items); setProjectTotal(result.data.total)
      if (!projectId) return
      const tableResult = await apiRequest<Schema['DataTablePage']>(`/v1/projects/${encodeURIComponent(projectId)}/tables?pageSize=100&page=${tablePage}`, { signal: controller.signal })
      if (stale()) return
      if (!tableResult.success || !tableResult.data) { setError('数据表读取失败，请重试'); return }
      setTables(tableResult.data.items); setTableTotal(tableResult.data.total)
      const selectedTable = tableResult.data.items.find(table => table.tableId === tableId)
      if (selectedTable && selectedTable.datasetGeneration !== grant?.datasetGeneration) { setError('数据表版本已变化，请重新选择数据表'); return }
      if (!tableId) return
      const fieldResult = await apiRequest<Schema['DataFieldDirectory']>(`/v1/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(tableId)}/fields`, { signal: controller.signal })
      if (stale()) return
      if (!fieldResult.success || !fieldResult.data) { setError('字段读取失败，请重试'); return }
      if (fieldResult.data.items.some(field => field.ref.projectId !== projectId || field.ref.tableId !== tableId || field.ref.datasetGeneration !== grant?.datasetGeneration)) {
        setError('数据表版本已变化，请重新选择数据表'); return
      }
      setFields(fieldResult.data.items)
      const statusResult = await apiRequest<Schema['DataStatusDirectory']>(`/v1/projects/${encodeURIComponent(projectId)}/tables/${encodeURIComponent(tableId)}/statuses`, { signal: controller.signal })
      if (stale()) return
      if (!statusResult.success || !statusResult.data) { setStatuses([]); setError('业务状态读取失败，请重试'); return }
      setStatuses(statusResult.data.items)
    }
    void load()
    return () => controller.abort()
  }, [projectId, tableId, grant?.datasetGeneration, origin, revision, projectPage, tablePage])
  function bind(table: Schema['DataTableView'], op = operation) {
    onChange('currentInputId', undefined)
    onChange('tableGrant', { tableId: table.tableId, datasetGeneration: table.datasetGeneration, operations: [op], fieldIds: [], readPurposes: readPurposes(op) })
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
    onChange('arguments', { recordRef: `{${ref}['recordRef']}`, ...(operation === 'readRecord' ? { fieldIds: ids, readPurpose: 'condition' } : operation === 'setRecordStatus' ? { expectedStatusRevision: `{${ref}['statusRevision']}`, statusId: null } : { changes: {} }) })
  }
  return <div className="space-y-4">
    <p className="text-sm text-muted-foreground">从项目自动化批次运行。使用任务的输入快照和数据权限，表发生重建时需要重新选择。</p>
    <Label htmlFor="project-data-operation">操作</Label>
    <Select id="project-data-operation" value={operation} onChange={event => {
      const next = event.target.value
      onChange('currentInputId', undefined); onChange('operation', next); onChange('argumentsValid', true); onChange('arguments', {}); onChange('tableGrant', undefined)
    }}>{retired ? <option value={operation} disabled>{retired}（已停用）</option> : null}{Object.entries(operations).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>
    {retired ? <p role="alert" className="text-sm text-danger">运行中不再修改表结构，请在项目「数据」页维护字段，然后把这个节点改为读取或写入记录，或删除它。</p> : null}
    {automation && ['readRecord', 'updateRecord', 'setRecordStatus'].includes(operation) && <><Label htmlFor="project-current-input">当前输入对象</Label><Select id="project-current-input" value={String(data.currentInputId ?? '')} onChange={event => selectInput(event.target.value)}><option value="">选择本次任务的输入对象</option>{automation.inputPlan.inputs.map(input => <option key={input.inputId} value={input.inputId}>{input.alias}</option>)}</Select></>}
    {tableId && operation === 'setRecordStatus' && <><Label htmlFor="project-input-status">设置为</Label><Select id="project-input-status" value={String(argumentsValue?.statusId ?? '')} onChange={event => writeForm({ statusId: event.target.value || null }, [])}><option value="">未设置</option>{statuses.map(status => <option key={status.statusId} value={status.statusId}>{status.name}</option>)}</Select></>}
    {operation !== 'inputs' && <>
      <Label htmlFor="project-data-project">所属项目</Label>
      <Select id="project-data-project" value={projectId} onChange={event => { setTablePage(1); onChange('currentInputId', undefined); onChange('bindingProjectId', event.target.value); onChange('tableGrant', undefined); onChange('arguments', {}) }}>
        <option value="">选择项目</option>{projects.map(project => <option key={project.projectId} value={project.projectId}>{project.name}</option>)}
      </Select>
      {projectTotal > 100 && <div className="flex gap-2"><button type="button" aria-label="项目列表上一页" disabled={projectPage === 1} onClick={() => setProjectPage(value => value - 1)}>上一页</button><span>第 {projectPage} 页</span><button type="button" aria-label="项目列表下一页" disabled={projectPage * 100 >= projectTotal} onClick={() => setProjectPage(value => value + 1)}>下一页</button></div>}
      <Label htmlFor="project-data-table">授权数据表</Label>
      <Select id="project-data-table" value={tableId} onChange={event => { const table = tables.find(item => item.tableId === event.target.value); if (table) bind(table) }}>
        <option value="">选择数据表</option>{tables.map(table => <option key={table.tableId} value={table.tableId}>{table.name}</option>)}
      </Select>
      {tableTotal > 100 && <div className="flex gap-2"><button type="button" aria-label="数据表列表上一页" disabled={tablePage === 1} onClick={() => setTablePage(value => value - 1)}>上一页</button><span>第 {tablePage} 页</span><button type="button" aria-label="数据表列表下一页" disabled={tablePage * 100 >= tableTotal} onClick={() => setTablePage(value => value + 1)}>下一页</button></div>}
      {tableId && fields.length > 0 && operation === 'createRecord' && <><Label>写入内容</Label><FieldValueRows key={tableId} fields={fields} value={argumentsValue?.values} onChange={values => writeForm({ values }, Object.keys(values))} /></>}
      {tableId && fields.length > 0 && operation === 'updateRecord' && <><Label>更新内容</Label><FieldValueRows key={tableId} fields={fields} value={argumentsValue?.changes} onChange={changes => writeForm({ changes }, Object.keys(changes))} /></>}
      {tableId && fields.length > 0 && operation === 'queryRecords' && <>
        <Label>查询条件</Label><ConditionRows key={tableId} fields={fields} filter={argumentsValue?.filter} onChange={filter => writeForm({ filter }, [...new Set([...returned, ...filterFieldIds(filter)])])} />
        <ReturnFields fields={fields} selected={returned} onChange={ids => writeForm({ fieldIds: ids }, [...new Set([...ids, ...filterFieldIds(conditionsFilter(argumentsValue?.filter))])])} />
      </>}
      {!isForm && fields.length > 0 && <fieldset><legend>允许访问的字段</legend>{fields.map(field => <label className="flex gap-2" key={field.ref.fieldId}>
        <input type="checkbox" checked={grant?.fieldIds.includes(field.ref.fieldId) ?? false} onChange={event => {
          const fieldIds = event.target.checked ? [...(grant?.fieldIds ?? []), field.ref.fieldId] : (grant?.fieldIds ?? []).filter(id => id !== field.ref.fieldId)
          onChange('tableGrant', { ...grant, operations: [operation], readPurposes: readPurposes(operation), fieldIds })
          if (operation === 'readRecord' || operation === 'queryRecords' || operation === 'queryTableSchema') onChange('arguments', { ...(data.arguments as Record<string, unknown>), fieldIds })
        }} />{field.name}
      </label>)}</fieldset>}
      {<button type="button" className="text-sm underline" aria-expanded={showAdvanced} onClick={() => setShowAdvanced(value => !value)}>高级：直接编辑参数</button>}
      {showAdvanced && <Arguments key={JSON.stringify(data.arguments)} value={data.arguments} onChange={value => { onChange('argumentsValid', true); onChange('arguments', value) }} onInvalid={() => onChange('argumentsValid', false)} />}
    </>}
    {error && <p role="alert">{error} <button type="button" onClick={() => refresh(value => value + 1)}>重试</button></p>}
    <Label htmlFor="project-data-result">结果变量</Label>
    <VariableInput id="project-data-result" value={String(data.variableName ?? '')} onChange={value => onChange('variableName', value)} placeholder="例如 saved_record" />
  </div>
}

const conditionsFilter = (filter: unknown) => filter && typeof filter === 'object' && Array.isArray((filter as { items?: unknown }).items) ? filter as Record<string, unknown> : null

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
    // Remediation M2 R2-24: new update nodes write without a version; conflicts are checked per field.
    case 'updateRecord': return { recordRef, changes: {} }
    case 'deleteRecord': return { recordRef, expectedContentRevision, expectedStatusRevision: "{record['statusRevision']}", expectedLinkRevision: "{record['linkRevision']}" }
    case 'setRecordStatus': return { recordRef, statusId: null, expectedStatusRevision: "{record['statusRevision']}" }
    default: return { ...identity }
  }
}
