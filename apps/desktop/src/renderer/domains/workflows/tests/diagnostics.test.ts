import { describe, expect, it } from 'vitest'
import { collectIssues } from '../diagnostics'
import { createWorkflow } from '../editor-model'
import type { NodeDefinition, WorkflowContent, WorkflowNode, WorkflowVariable } from '../types'

const text = { type: 'string' }
const catalog: NodeDefinition[] = [
  { type: 'open_page', properties: { url: text, openMode: { type: 'string', enum: ['new_tab', 'current_tab'] }, waitUntil: { type: 'string', enum: ['load', 'domcontentloaded', 'networkidle'] } }, required: ['url'] },
  { type: 'input_text', properties: { selector: text, text, clearBefore: { type: 'boolean' } }, required: ['selector'] },
  { type: 'get_element_info', properties: { selector: text, variableName: text, attribute: { type: 'string', enum: ['text', 'innerHTML', 'value', 'href', 'src', 'attributes'] } }, required: ['selector', 'variableName'] },
  { type: 'screenshot', properties: { selector: text, savePath: text, variableName: text, screenshotType: { type: 'string', enum: ['fullpage', 'viewport', 'element'] } }, required: ['variableName'] },
].map((entry) => ({ type: entry.type as NodeDefinition['type'], title: entry.type, description: '', category: '浏览器', defaultConfig: {}, configSchema: { type: 'object', properties: { ...entry.properties, timeoutSeconds: { type: 'number', exclusiveMinimum: 0, default: 60 } }, required: entry.required, additionalProperties: false }, inputPorts: ['in'], outputPorts: ['out'], runnable: false }))

function node(id: string, type: WorkflowNode['type'] = 'open_page', config: Record<string, unknown> = { url: 'https://example.test' }): WorkflowNode {
  return { id, type, label: id, config }
}

function flow(nodes: WorkflowNode[], variables: WorkflowVariable[] = [], pairs: [string, string][] = []): WorkflowContent {
  const content = createWorkflow()
  content.document.nodes = nodes
  content.document.variables = variables
  content.document.edges = pairs.map(([source, target], index) => ({ id: `e-${index}`, source, target, sourceHandle: 'out', targetHandle: 'in' }))
  content.layout.nodes = Object.fromEntries(nodes.map((item, index) => [item.id, { x: index * 100, y: 0 }]))
  return content
}

const diagnostics = (content: WorkflowContent) => collectIssues(content, catalog).map(({ nodeId, path, code }) => ({ nodeId, path, code }))

describe('workflow draft diagnostics', () => {
  it('identifies disconnected components even when every node has an edge', () => {
    const content = flow(['a', 'b', 'c', 'd'].map((id) => node(id)), [], [['a', 'b'], ['c', 'd']])
    expect(diagnostics(content)).toEqual([
      { nodeId: 'c', path: ['edges'], code: 'DISCONNECTED_NODE' },
      { nodeId: 'd', path: ['edges'], code: 'DISCONNECTED_NODE' },
    ])
    content.document.edges.push({ id: 'join', source: 'b', target: 'c', sourceHandle: 'out', targetHandle: 'in' })
    expect(diagnostics(content)).toEqual([])
  })

  it.each(['example.test', 'file:///tmp/page.html', 'https://', 'https://@', 'https://bad host/', 'https://[wrong]/'])('reports an invalid literal URL: %s', (url) => {
    expect(diagnostics(flow([node('a', 'open_page', { url })]))).toEqual([{ nodeId: 'a', path: ['config', 'url'], code: 'INVALID_URL' }])
  })

  it.each(['https://example.test/path', 'HTTPS://example.test:bad/', 'http://localhost', 'http://[::1]:8000/', '${地址}/path', '{地址}'])('accepts an HTTP URL or declared variable template: %s', (url) => {
    expect(diagnostics(flow([node('a', 'open_page', { url })], [{ name: '地址', type: 'string', value: 'https://example.test' }]))).toEqual([])
  })

  it('keeps empty input text valid and requires an element screenshot selector only in element mode', () => {
    expect(diagnostics(flow([node('a', 'input_text', { selector: '#search', text: '', clearBefore: true, timeoutSeconds: 60 })]))).toEqual([])
    const content = flow([node('a', 'screenshot', { screenshotType: 'element', selector: '', savePath: '', variableName: '' })])
    expect(diagnostics(content)).toEqual([
      { nodeId: 'a', path: ['config', 'variableName'], code: 'REQUIRED' },
      { nodeId: 'a', path: ['config', 'selector'], code: 'REQUIRED' },
    ])
    content.document.nodes[0].config = { screenshotType: 'fullpage', selector: '', savePath: '', variableName: 'shot' }
    expect(diagnostics(content)).toEqual([])
  })

  it('does not silently accept null, wrong types, invalid enum values, unknown fields or invalid timeouts', () => {
    const content = flow([node('a', 'open_page', { url: null, openMode: true, waitUntil: 'ready', timeoutSeconds: 0, legacy: 'value' })])
    expect(diagnostics(content)).toEqual([
      { nodeId: 'a', path: ['config', 'url'], code: 'REQUIRED' },
      { nodeId: 'a', path: ['config', 'url'], code: 'INVALID_CONFIG_TYPE' },
      { nodeId: 'a', path: ['config', 'openMode'], code: 'INVALID_CONFIG_TYPE' },
      { nodeId: 'a', path: ['config', 'waitUntil'], code: 'INVALID_CONFIG_VALUE' },
      { nodeId: 'a', path: ['config', 'timeoutSeconds'], code: 'INVALID_TIMEOUT' },
      { nodeId: 'a', path: ['config', 'legacy'], code: 'UNKNOWN_CONFIG_FIELD' },
    ])
  })

  it('uses Unicode variable names and reports duplicate outputs without renaming or rejecting drafts', () => {
    const content = flow([
      node('a', 'get_element_info', { selector: '${选择器}', variableName: '结果', attribute: 'text' }),
      node('b', 'screenshot', { screenshotType: 'fullpage', savePath: '{结果}', variableName: '结果' }),
    ], [{ name: '选择器', type: 'string', value: '#result' }], [['a', 'b']])
    const before = structuredClone(content)
    expect(diagnostics(content)).toEqual([
      { nodeId: 'a', path: ['config', 'variableName'], code: 'DUPLICATE_OUTPUT_VARIABLE' },
      { nodeId: 'b', path: ['config', 'variableName'], code: 'DUPLICATE_OUTPUT_VARIABLE' },
    ])
    expect(content).toEqual(before)
  })

  it('locates missing and malformed references in nested values, deduplicating only within each text', () => {
    const content = flow([node('a', 'input_text', { selector: '#input', text: '{missing} ${missing} ${bad-name} {{credential:key}}', clearBefore: true })], [
      { name: '数据', type: 'object', value: { list: ['{missing}', '${bad-name}'] } },
    ])
    expect(diagnostics(content)).toEqual([
      { nodeId: null, path: ['variables', '0', 'value', 'list', '1'], code: 'INVALID_REFERENCE' },
      { nodeId: null, path: ['variables', '0', 'value', 'list', '0'], code: 'UNKNOWN_VARIABLE' },
      { nodeId: 'a', path: ['config', 'text'], code: 'UNKNOWN_VARIABLE' },
      { nodeId: 'a', path: ['config', 'text'], code: 'INVALID_REFERENCE' },
    ])
  })

  it('uses variable array indices in errors and retains mismatched initial values for saving', () => {
    const content = flow([node('a')], [
      { name: '重复', type: 'number', value: '' },
      { name: '重复', type: 'object', value: null },
      { name: '1bad', type: 'array', value: [] },
    ])
    expect(diagnostics(content)).toEqual([
      { nodeId: null, path: ['variables', '0', 'name'], code: 'DUPLICATE_VARIABLE' },
      { nodeId: null, path: ['variables', '0', 'value'], code: 'VARIABLE_TYPE_MISMATCH' },
      { nodeId: null, path: ['variables', '1', 'name'], code: 'DUPLICATE_VARIABLE' },
      { nodeId: null, path: ['variables', '1', 'value'], code: 'VARIABLE_TYPE_MISMATCH' },
      { nodeId: null, path: ['variables', '2', 'name'], code: 'INVALID_VARIABLE_NAME' },
    ])
  })

  it('keeps literal JSON and bare non-reference braces as text while rejecting explicit malformed references', () => {
    const content = flow([node('a', 'input_text', { selector: '#input', text: '{"answer":42} {bad.name} ${bad.name}' })])
    expect(diagnostics(content)).toEqual([{ nodeId: 'a', path: ['config', 'text'], code: 'INVALID_REFERENCE' }])
    content.document.nodes[0].config.text = '{"answer":42} {bad.name}'
    expect(diagnostics(content)).toEqual([])
    content.document.nodes[0] = node('a', 'open_page', { url: '{"url":"https://example.test"}' })
    expect(diagnostics(content)).toEqual([{ nodeId: 'a', path: ['config', 'url'], code: 'INVALID_URL' }])
  })

  it('reports empty workflows and unavailable node definitions', () => {
    expect(diagnostics(flow([]))).toEqual([{ nodeId: null, path: ['nodes'], code: 'EMPTY_WORKFLOW' }])
    expect(collectIssues(flow([node('a')]), []).map((issue) => issue.code)).toEqual(['UNKNOWN_NODE'])
  })
})
