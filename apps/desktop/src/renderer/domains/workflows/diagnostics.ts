import { controlTypes } from './control-model'
import { referencedVariables } from './editor-model'
import type { NodeDefinition, WorkflowContent, WorkflowIssue } from './types'

const referenceEnvelope = /\$\{([^{}]*)\}|(?<![${])\{([^{}]*)\}(?!\})/gu
const validName = (value: unknown): value is string => typeof value === 'string' && /^[\p{L}_][\p{L}\p{N}_]*$/u.test(value)

function matchesType(value: unknown, expected: string): boolean {
  if (expected === 'number') return typeof value === 'number' && Number.isFinite(value)
  if (expected === 'array') return Array.isArray(value)
  if (expected === 'object') return value !== null && typeof value === 'object' && !Array.isArray(value)
  return typeof value === expected
}

/** Match the sidecar's HTTP(S), hostname and authority checks, without DNS access. */
function validUrl(value: string): boolean {
  const match = /^[\u0000-\u0020]*https?:\/\/([^/?#]*)/i.exec(value.replace(/[\r\n\t]/g, ''))
  if (!match || !match[1] || /\s/u.test(match[1])) return false
  const hostPort = match[1].slice(match[1].lastIndexOf('@') + 1)
  if (hostPort.startsWith('[')) {
    const closing = hostPort.indexOf(']')
    if (closing < 0) return false
    const host = hostPort.slice(1, closing)
    if (/^v[\da-f]+\..+$/i.test(host)) return true
    try {
      // The backend accepts scoped IPv6 literals; their scope is not part of the IP.
      return new URL(`http://[${host.split('%')[0]}]/`).hostname.includes(':')
    } catch { return false }
  }
  return !/[\[\]]/.test(hostPort) && Boolean(hostPort.split(':')[0])
}

type ConfigSchema = { required?: string[]; properties?: Record<string, { type: string; enum?: unknown[] }> }

/** Draft diagnostics mirror domain/workflows/validation.py; they never block persistence. */
export function collectIssues(content: WorkflowContent, catalog: NodeDefinition[]): WorkflowIssue[] {
  const issues: WorkflowIssue[] = []
  const { nodes, edges, variables } = content.document
  const issue = (code: string, message: string, path: string[], nodeId: string | null = null) => issues.push({ nodeId, path, code, message })
  const definitions = new Map(catalog.map((definition) => [definition.type, definition]))
  const counts = new Map<string, number>()
  for (const variable of variables) counts.set(variable.name, (counts.get(variable.name) ?? 0) + 1)
  const names = new Set(variables.map((variable) => variable.name).filter(validName))
  const outputs = new Map<string, number>()
  for (const node of nodes) {
    const name = node.config.variableName
    if (validName(name)) { names.add(name); outputs.set(name, (outputs.get(name) ?? 0) + 1) }
  }
  for (const node of nodes) if (node.type === 'loop') for (const field of node.config.mode === 'foreach' ? ['indexVariable', 'itemVariable'] : ['indexVariable']) { const name = node.config[field]; if (validName(name)) names.add(name) }
  const checkReferences = (value: unknown, path: string[], nodeId: string | null = null) => {
    const pending: { value: unknown; path: string[] }[] = [{ value, path }]
    while (pending.length) {
      const current = pending.pop()!
      if (current.value && typeof current.value === 'object') {
        const source = current.value as Record<string, unknown>
        if (nodeId !== null && source.kind === 'literal') continue
        if (nodeId !== null && source.kind === 'variable') { if (!names.has(String(source.name))) issue('UNKNOWN_VARIABLE', `变量 ${String(source.name)} 尚未声明`, [...current.path, 'name'], nodeId); continue }
        for (const [key, child] of Object.entries(current.value)) pending.push({ value: child, path: [...current.path, key] })
      } else if (typeof current.value === 'string') {
        const recognized = new Set(referencedVariables(current.value))
        const seen = new Set<string>()
        for (const match of current.value.matchAll(referenceEnvelope)) {
          const name = match[1] ?? match[2]
          if (!recognized.has(name) && match[1] === undefined) continue
          if (seen.has(name)) continue
          seen.add(name)
          if (!recognized.has(name)) issue('INVALID_REFERENCE', '变量引用须使用 {变量名} 或 ${变量名}', current.path, nodeId)
          else if (!names.has(name)) issue('UNKNOWN_VARIABLE', `变量 ${name} 尚未声明`, current.path, nodeId)
        }
      }
    }
  }
  variables.forEach((variable, index) => {
    const path = ['variables', String(index)]
    if (!validName(variable.name)) issue('INVALID_VARIABLE_NAME', '变量名须为有效标识符', [...path, 'name'])
    if (counts.get(variable.name)! > 1) issue('DUPLICATE_VARIABLE', '变量名称重复', [...path, 'name'])
    if (!matchesType(variable.value, variable.type)) issue('VARIABLE_TYPE_MISMATCH', '变量值与声明类型不符', [...path, 'value'])
    checkReferences(variable.value, [...path, 'value'])
  })
  for (const node of nodes) {
    const definition = definitions.get(node.type)
    if (!definition) { issue('UNKNOWN_NODE', '节点定义尚不可用', [], node.id); continue }
    if (node.type === 'loop') {
      if (!Number.isInteger(node.config.maxIterations) || Number(node.config.maxIterations) < 1 || Number(node.config.maxIterations) > 100000) issue('LOOP_LIMIT_INVALID', '循环上限须为 1 至 100000 的整数', ['config', 'maxIterations'], node.id)
      for (const field of node.config.mode === 'foreach' ? ['indexVariable', 'itemVariable'] : ['indexVariable']) if (!validName(node.config[field])) issue('LOOP_VARIABLE_INVALID', '循环变量名无效', ['config', field], node.id)
    }
    if (['loop', 'condition'].includes(node.type)) {
      const end = nodes.find(n => n.id === node.config.endNodeId)
      if (!end || end.type !== `${node.type}_end` || end.config.ownerNodeId !== node.id) issue('BLOCK_PAIR_INVALID', '控制块缺少正确配对的结束节点', ['config', 'endNodeId'], node.id)
      for (const port of node.type === 'condition' ? ['true', 'false'] : ['body']) if (!edges.some(e => e.source === node.id && e.sourceHandle === port)) issue('BLOCK_NOT_CONNECTED', '请连接控制块分支或循环体', ['edges', port], node.id)
    }
    if (controlTypes.has(node.type)) {
      const pending = [{ value: node.config as unknown, path: ['config'] }]
      while (pending.length) {
        const current = pending.pop()!
        if (!current.value || typeof current.value !== 'object') continue
        const source = current.value as Record<string, unknown>
        if (source.kind === 'literal') { if (typeof source.valueType === 'string' && (source.valueType === 'null' ? source.value !== null : !matchesType(source.value, source.valueType))) issue('VALUE_TYPE_MISMATCH', '固定值与所选类型不符，请完成输入', [...current.path, 'value'], node.id); continue }
        if (source.kind === 'page' && (typeof source.selector !== 'string' || !source.selector.trim())) issue('REQUIRED', '请填写元素选择器', [...current.path, 'selector'], node.id)
        for (const [key, value] of Object.entries(source)) pending.push({ value, path: [...current.path, key] })
      }
    }
    const schema = definition.configSchema as ConfigSchema
    const required = new Set(schema.required ?? [])
    if (node.type === 'screenshot' && node.config.screenshotType === 'element') required.add('selector')
    for (const field of required) {
      const value = node.config[field]
      if (value === undefined || value === null || (typeof value === 'string' && !value.trim())) issue('REQUIRED', '此字段尚未填写', ['config', field], node.id)
    }
    for (const [field, value] of Object.entries(node.config)) {
      const path = ['config', field]
      if (field !== 'variableName' && !(node.type === 'screenshot' && node.config.screenshotType !== 'element' && ['selector', 'framePath'].includes(field))) checkReferences(value, path, node.id)
      const rule = schema.properties?.[field]
      if (!rule) { issue('UNKNOWN_CONFIG_FIELD', '此节点不支持该配置字段', path, node.id); continue }
      if (!matchesType(value, rule.type)) { issue('INVALID_CONFIG_TYPE', '配置值类型不符', path, node.id); continue }
      if (field === 'framePath' && Array.isArray(value)) value.forEach((step, index) => { if (typeof step !== 'string' || !step.trim()) issue('INVALID_FRAME_PATH', '框架路径须为非空选择器', [...path, String(index)], node.id) })
      if (rule.enum && !rule.enum.includes(value)) issue('INVALID_CONFIG_VALUE', '请选择有效选项', path, node.id)
      if (field === 'timeoutSeconds' && typeof value === 'number' && value <= 0) issue('INVALID_TIMEOUT', '超时须大于 0 秒', path, node.id)
      if (field === 'variableName' && value && !validName(value)) issue('INVALID_VARIABLE_NAME', '输出变量名须为有效标识符', path, node.id)
      if (field === 'variableName' && validName(value) && (outputs.get(value) ?? 0) > 1) issue('DUPLICATE_OUTPUT_VARIABLE', '多个节点写入同名变量，运行时可能覆盖', path, node.id)
      if (field === 'url' && typeof value === 'string' && value && ![...value.matchAll(referenceEnvelope)].some((match) => match[1] !== undefined || validName(match[2])) && !validUrl(value)) issue('INVALID_URL', '请输入 HTTP/HTTPS 网址或变量引用', path, node.id)
    }
  }
  if (!nodes.length) issue('EMPTY_WORKFLOW', '添加节点后开始编排', ['nodes'])
  else if (nodes.length > 1 && !nodes.some(n => controlTypes.has(n.type))) {
    const neighbors = new Map(nodes.map((node) => [node.id, new Set<string>()]))
    for (const edge of edges) {
      neighbors.get(edge.source)?.add(edge.target)
      neighbors.get(edge.target)?.add(edge.source)
    }
    const reachable = new Set<string>()
    const pending = [nodes[0].id]
    while (pending.length) {
      const current = pending.pop()!
      if (!reachable.has(current)) { reachable.add(current); pending.push(...neighbors.get(current) ?? []) }
    }
    if (reachable.size !== nodes.length) for (const node of nodes) {
      if (!neighbors.get(node.id)?.size || !reachable.has(node.id)) issue('DISCONNECTED_NODE', '节点尚未连接到同一条流程', ['edges'], node.id)
    }
  }
  return issues
}
