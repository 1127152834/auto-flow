import { expect, it } from 'vitest'
import schema from '../generated/executor-config-keys.json'
import { describeUnknownSettings, findUnknownSettings, unknownConfigKeys } from '../lib/unknownConfigKeys'

// Same cases as apps/backend/tests/unit/workflows/test_config_schema.py (remediation M2 R2-11).
it('reports only keys that neither the executor nor the node panel uses', () => {
  const data = { label: '复制', variableName: 'x', variableValue: '1', timeout: 3, selector: '#a', config: { waitUntil: 'load' } }
  expect(unknownConfigKeys(data, 'set_variable')).toEqual(['selector', 'waitUntil'])
  expect(unknownConfigKeys({ apiKey: 'k', userPrompt: 'hi' }, 'ai_chat')).toEqual([])
  expect(unknownConfigKeys({ color: 'red', whatever: 1 }, 'group')).toEqual([])
  expect(unknownConfigKeys({ anything: 1 }, 'project_data')).toEqual([])
})

it('describes the nodes in plain words', () => {
  const found = findUnknownSettings([{ id: 'a', data: { moduleType: 'set_variable', label: '赋值', variableName: 'x', selector: '#a' } }, { id: 'b', data: { moduleType: 'set_variable', variableName: 'y' } }])
  expect(found).toEqual([{ nodeId: 'a', label: '赋值', keys: ['selector'] }])
  expect(describeUnknownSettings(found)).toBe('以下设置不会被运行读取，可能来自其他版本或其他节点类型：「赋值」selector')
})

it('never warns about a node exactly as the editor creates it, and the unread defaults list is exact', async () => {
  const { useWorkflowStore: store, moduleTypeLabels } = await import('../editor-store')
  const nodes = schema.nodes as Record<string, { reads: string[]; panelOnly: string[]; editorDefaults: string[] }>
  const unreadDefaults: Record<string, string[]> = {}
  for (const type of Object.keys(moduleTypeLabels)) {
    store.getState().clearWorkflow()
    store.getState().addNode(type as never, { x: 0, y: 0 })
    expect(findUnknownSettings(store.getState().nodes), type).toEqual([])
    const known = nodes[type]
    if (!known || type === 'group' || type === 'note') continue  // canvas-only, never executed
    const data = store.getState().nodes[0].data as Record<string, unknown>
    const unread = Object.keys(data).filter(key => !known.reads.includes(key) && !schema.commonKeys.includes(key) && !known.panelOnly.includes(key)).sort()
    if (unread.length) unreadDefaults[type] = unread
  }
  // Shrinks only: remove fixed entries from config_schema_debt.EDITOR_DEFAULT_KEYS and regenerate.
  const frozen = Object.fromEntries(Object.entries(nodes).filter(([, value]) => value.editorDefaults.length).map(([type, value]) => [type, value.editorDefaults]))
  expect(unreadDefaults).toEqual(frozen)
})
