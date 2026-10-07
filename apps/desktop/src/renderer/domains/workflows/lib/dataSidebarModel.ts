// Data sidebar model (R5-13): signature inputs, node outputs, global variables and credentials as plain rows.
// Rows carry the reference text a click copies; selectors tell which canvas nodes use which row.
import { moduleTypeLabels } from '../editor-store'
import { SENSITIVE_SAMPLE_MASK } from './dataReferences'
import { declaredOutputs, outputAvailability } from './nodeOutputs'
import type { SignatureInputDraft } from './signatureDocument'

export type DataGroupId = 'inputs' | 'nodeOutputs' | 'variables' | 'credentials'
export type DataRow = {
  key: string
  group: DataGroupId
  title: string
  subgroup?: string
  type?: string
  source: string
  required?: boolean
  availability?: 'always' | 'conditional'
  sample?: string
  sensitive?: boolean
  description?: string
  copyText: string
  /** True when copyText is a reference that nodes can use; credentials only copy their name. */
  isReference: boolean
}
export type DataNode = { id: string; data?: unknown }
export type DataEdge = { source: string; target: string; sourceHandle?: string | null }
export type DataVariable = { name: string; value: unknown; type: string; scope: string }
export type DataCredential = { name: string; description?: string }
export type DataSidebarInput = {
  signature: SignatureInputDraft[]; nodes: DataNode[]; edges: DataEdge[]; variables: DataVariable[]; credentials: DataCredential[]
}

const TYPE_LABELS: Record<string, string> = { string: '文本', number: '数字', boolean: '是/否', date: '日期', any: '任意', array: '列表', object: '对象' }
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const typeLabel = (type: string) => TYPE_LABELS[type] ?? type
const clip = (text: string, max = 30) => text.length > max ? `${text.slice(0, max)}…` : text
function show(value: unknown) {
  if (value === undefined || value === null || value === '') return '（空）'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return clip(typeof value === 'object' ? JSON.stringify(value) : String(value))
}

export function nodeTitles(nodes: DataNode[]) {
  const titleOf = (node: DataNode) => isRecord(node.data) ? String(node.data.label || node.data.name || (moduleTypeLabels as Record<string, string>)[String(node.data.moduleType)] || node.data.moduleType || '') : ''
  const total = new Map<string, number>()
  for (const node of nodes) total.set(titleOf(node), (total.get(titleOf(node)) ?? 0) + 1)
  const seen = new Map<string, number>()
  return new Map(nodes.map(node => {
    const title = titleOf(node), index = (seen.get(title) ?? 0) + 1
    seen.set(title, index)
    return [node.id, total.get(title)! > 1 ? `${title}（第 ${index} 个）` : title] as const
  }))
}

function inputRows(signature: SignatureInputDraft[]): DataRow[] {
  return signature.flatMap(input => input.fields.map<DataRow>(field => ({
    key: `input.${input.key}.${field.key}`, group: 'inputs', title: field.name, subgroup: input.name, type: typeLabel(field.type), source: `流程输入·${input.name}`,
    required: field.required, sensitive: field.sensitive,
    sample: field.sensitive ? SENSITIVE_SAMPLE_MASK : field.sample === undefined ? undefined : show(field.sample),
    copyText: `{input.${input.key}.${field.key}}`, isReference: true,
  })))
}

function nodeOutputRows({ nodes, edges }: DataSidebarInput): DataRow[] {
  const titles = nodeTitles(nodes)
  const verdicts = new Map<string, boolean>()
  for (const target of nodes) {
    for (const output of outputAvailability(nodes, edges, target.id)) {
      const id = `${output.nodeId}\0${output.key}`
      verdicts.set(id, (verdicts.get(id) ?? true) && output.required)
    }
  }
  return nodes.flatMap(node => {
    if (!isRecord(node.data)) return []
    return declaredOutputs(String(node.data.moduleType)).map<DataRow>(output => {
      const verdict = verdicts.get(`${node.id}\0${output.key}`)
      return {
        key: `node.${node.id}.${output.key}`, group: 'nodeOutputs', title: `${titles.get(node.id)}·${output.name}`, source: titles.get(node.id)!,
        sensitive: output.sensitive, sample: output.sensitive ? SENSITIVE_SAMPLE_MASK : undefined,
        availability: verdict === undefined ? undefined : verdict ? 'always' : 'conditional',
        copyText: `{node.${node.id}.${output.key}}`, isReference: true,
      }
    })
  })
}

export function buildDataSidebar(input: DataSidebarInput): Record<DataGroupId, DataRow[]> {
  return {
    inputs: inputRows(input.signature),
    nodeOutputs: nodeOutputRows(input),
    variables: input.variables.filter(variable => variable.scope === 'global').map<DataRow>(variable => ({
      key: `variable.${variable.name}`, group: 'variables', title: variable.name, type: typeLabel(variable.type), source: '全局变量', sample: show(variable.value),
      copyText: `{${variable.name}}`, isReference: true,
    })),
    credentials: input.credentials.map<DataRow>(credential => ({
      key: `credential.${credential.name}`, group: 'credentials', title: credential.name, source: '凭据', description: credential.description || undefined,
      copyText: credential.name, isReference: false,
    })),
  }
}

export function filterRows(rows: DataRow[], query: string) {
  const needle = query.trim().toLowerCase()
  if (!needle) return rows
  return rows.filter(row => [row.title, row.subgroup, row.source, row.description].some(text => text?.toLowerCase().includes(needle)))
}

// Match against the string leaves of the node data, so quotes or backslashes in a reference are not JSON-escaped away.
function mentions(value: unknown, text: string): boolean {
  if (typeof value === 'string') return value.includes(text)
  if (Array.isArray(value)) return value.some(item => mentions(item, text))
  if (isRecord(value)) return Object.values(value).some(item => mentions(item, text))
  return false
}

/** Ids of canvas nodes whose settings use this reference text. */
export function nodesReferencing(nodes: DataNode[], reference: string) {
  return nodes.filter(node => mentions(node.data, reference)).map(node => node.id)
}

/** Reference texts of the given rows that this node uses. */
export function referencesInNode(node: DataNode, rows: DataRow[]) {
  return rows.filter(row => row.isReference && mentions(node.data, row.copyText)).map(row => row.copyText)
}
