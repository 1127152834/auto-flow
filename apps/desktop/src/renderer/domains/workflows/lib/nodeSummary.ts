// Node summary shared by the canvas node and the block view: the action target, plus the data the node uses.
// Pure functions; references are shown with business names from dataReferences.
import { parseReferences, referenceLabel, type ReferenceContext, type ReferencePart } from './dataReferences'

type NodeLike = Record<string, unknown>
export type RefPart = Extract<ReferencePart, { type: 'ref' }>
export type NodeSummary = { parts: ReferencePart[]; text: string }

const TARGET_KEYS = ['url', 'selector', 'text', 'logMessage', 'variableName', 'userPrompt', 'requestUrl', 'value', 'filePath', 'inputPath', 'message', 'resultVariable', 'condition', 'count', 'listVariable']
const SKIPPED_KEYS = new Set(['projectInputTypes', 'label', 'name'])
const READ_OPERATIONS = new Set(['inputs', 'readRecord', 'queryRecords', 'queryTableSchema'])
const WRITE_OPERATIONS = new Set(['createRecord', 'updateRecord', 'deleteRecord', 'setRecordStatus'])
const filled = (value: unknown): value is string => typeof value === 'string' && value.trim() !== ''

function targetText(data: NodeLike) {
  if (data.moduleType === 'subflow' && filled(data.subflowName)) return data.subflowName
  for (const key of TARGET_KEYS) if (filled(data[key])) return key === 'variableName' ? `→ ${data[key]}` : data[key] as string
  return ''
}

function clip(parts: ReferencePart[], max: number): ReferencePart[] {
  const result: ReferencePart[] = []
  let used = 0
  for (const part of parts) {
    const label = referenceLabel(part)
    if (used + label.length <= max) { result.push(part); used += label.length; continue }
    if (part.type === 'text' && max > used) result.push({ type: 'text', text: label.slice(0, max - used) })
    result.push({ type: 'text', text: '…' })
    break
  }
  return result
}

export function summarizeNode(data: NodeLike, context: ReferenceContext, max = 30): NodeSummary {
  const parts = clip(parseReferences(targetText(data), context), max)
  return { parts, text: parts.map(referenceLabel).join('') }
}

function strings(value: unknown, out: string[]) {
  if (typeof value === 'string') out.push(value)
  else if (Array.isArray(value)) value.forEach(item => strings(item, out))
  else if (typeof value === 'object' && value !== null) for (const [key, item] of Object.entries(value)) if (!SKIPPED_KEYS.has(key)) strings(item, out)
}

/** References the node's settings use, once each. Unknown {name} text stays out: code and patterns use braces too. */
export function nodeDataTags(data: NodeLike, context: ReferenceContext, shown?: NodeSummary): RefPart[] {
  const texts: string[] = []
  strings(data, texts)
  const skip = new Set(shown?.parts.flatMap(part => part.type === 'ref' ? [part.raw] : []))
  const tags = new Map<string, RefPart>()
  for (const text of texts) for (const part of parseReferences(text, context)) {
    if (part.type === 'ref' && !skip.has(part.raw) && !tags.has(part.raw) && (part.valid || part.kind !== 'variable')) tags.set(part.raw, part)
  }
  return [...tags.values()]
}

/** Whether the node reads data (uses a reference, or reads project data) and whether it writes project data. */
export function dataAccess(data: NodeLike, tags: unknown[]) {
  const operation = data.moduleType === 'project_data' ? String(data.operation ?? 'inputs') : ''
  return { read: tags.length > 0 || READ_OPERATIONS.has(operation), write: WRITE_OPERATIONS.has(operation) }
}
