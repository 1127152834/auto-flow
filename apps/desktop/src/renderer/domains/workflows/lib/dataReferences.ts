// Shared parser for data references in node text: turns the four reference formats into business labels.
// Pure functions, no store or React imports. Formats: {input.<group>.<field>}, {node.<nodeId>.<key>},
// legacy PROJECT_INPUTS['<id>']['values']['<id>'], and legacy {variableName} (kept until M6).
export type ReferenceKind = 'input' | 'node' | 'legacyInput' | 'variable'
export type ReferenceContext = {
  signature?: Record<string, { label?: string; fields?: Record<string, { label?: string; type?: string; sensitive?: boolean; sample?: string }> }>
  nodeOutputs?: { nodeId: string; key: string; name: string; label: string; type?: string; sensitive?: boolean; sample?: string }[]
  variables?: Record<string, { type?: string; sensitive?: boolean; sample?: string }>
  inputs?: { inputId: string; alias: string; fields?: { fieldId: string; alias: string; type?: string; sensitive?: boolean }[] }[]
}
export type ReferencePart =
  | { type: 'text'; text: string }
  | { type: 'ref'; raw: string; kind: ReferenceKind; display: string; valid: boolean; dataType?: string; source?: string; sample?: string; sensitive?: boolean }

export const INVALID_REFERENCE_LABEL = '已失效的引用'
export const SENSITIVE_SAMPLE_MASK = '••••••'

const PATTERN = new RegExp([
  String.raw`(?<esc>\\[{}])`,
  String.raw`\$?\{\s*input\.(?<group>[^.{}\s]+)(?:\.(?<field>[^.{}\s]+))?\s*\}`,
  String.raw`\$?\{\s*node\.(?<node>[^.{}\s]+)\.(?<key>[^.{}\s]+)\s*\}`,
  String.raw`PROJECT_INPUTS\['(?<inputId>[^']*)'\](?:\['values'\]\['(?<fieldId>[^']*)'\])?`,
  String.raw`\{(?<name>[^{}\s.]+)\}`,
].join('|'), 'g')

const mask = (sensitive: boolean | undefined, sample: string | undefined) => sample === undefined ? undefined : sensitive ? SENSITIVE_SAMPLE_MASK : sample
const join = (...names: (string | undefined)[]) => names.filter(Boolean).join('·')

export function parseReferences(text: string, context: ReferenceContext = {}): ReferencePart[] {
  const parts: ReferencePart[] = []
  const pushText = (value: string) => {
    if (!value) return
    const last = parts[parts.length - 1]
    if (last?.type === 'text') last.text += value
    else parts.push({ type: 'text', text: value })
  }
  let cursor = 0
  for (const match of text.matchAll(PATTERN)) {
    pushText(text.slice(cursor, match.index))
    cursor = match.index + match[0].length
    const g = match.groups!, raw = match[0]
    if (g.esc) pushText(g.esc.slice(1))
    else if (g.group) parts.push(inputRef(raw, g.group, g.field, context))
    else if (g.node) parts.push(nodeRef(raw, g.node, g.key, context))
    else if (g.inputId !== undefined) parts.push(legacyInputRef(raw, g.inputId, g.fieldId, context))
    else parts.push(variableRef(raw, g.name, context))
  }
  pushText(text.slice(cursor))
  return parts
}

function invalid(raw: string, kind: ReferenceKind): ReferencePart {
  return { type: 'ref', raw, kind, display: INVALID_REFERENCE_LABEL, valid: false }
}

function inputRef(raw: string, group: string, field: string | undefined, context: ReferenceContext): ReferencePart {
  const entry = context.signature?.[group]
  if (!entry) return invalid(raw, 'input')
  if (!field) return { type: 'ref', raw, kind: 'input', display: entry.label || group, valid: true, source: '流程输入' }
  const item = entry.fields?.[field]
  if (!item) return invalid(raw, 'input')
  return { type: 'ref', raw, kind: 'input', display: join(entry.label || group, item.label || field), valid: true, dataType: item.type, source: '流程输入', sample: mask(item.sensitive, item.sample), sensitive: item.sensitive }
}

function nodeRef(raw: string, nodeId: string, key: string, context: ReferenceContext): ReferencePart {
  const output = context.nodeOutputs?.find(item => item.nodeId === nodeId && item.key === key)
  if (!output) return invalid(raw, 'node')
  return { type: 'ref', raw, kind: 'node', display: join(output.label, output.name), valid: true, dataType: output.type, source: output.label, sample: mask(output.sensitive, output.sample), sensitive: output.sensitive }
}

function legacyInputRef(raw: string, inputId: string, fieldId: string | undefined, context: ReferenceContext): ReferencePart {
  const input = context.inputs?.find(item => item.inputId === inputId)
  if (!input) return invalid(raw, 'legacyInput')
  if (fieldId === undefined) return { type: 'ref', raw, kind: 'legacyInput', display: input.alias, valid: true, source: '项目数据' }
  const field = input.fields?.find(item => item.fieldId === fieldId)
  if (!field) return invalid(raw, 'legacyInput')
  return { type: 'ref', raw, kind: 'legacyInput', display: join(input.alias, field.alias), valid: true, dataType: field.type, source: '项目数据', sensitive: field.sensitive }
}

function variableRef(raw: string, name: string, context: ReferenceContext): ReferencePart {
  const variable = context.variables?.[name]
  return { type: 'ref', raw, kind: 'variable', display: name, valid: !!variable, dataType: variable?.type, source: '全局变量', sample: mask(variable?.sensitive, variable?.sample), sensitive: variable?.sensitive }
}

export function referenceLabel(part: ReferencePart) {
  return part.type === 'text' ? part.text : part.display
}

/** Text with every reference replaced by its business label. */
export function formatReference(text: string, context: ReferenceContext = {}) {
  return parseReferences(text, context).map(referenceLabel).join('')
}
