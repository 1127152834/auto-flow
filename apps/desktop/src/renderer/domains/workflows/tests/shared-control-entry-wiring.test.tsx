import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import toolCases from '../../../../../../../docs/migration/studio-frontend-completion/evidence/f2-tool-entries/cases.json'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

type StringControlProps = { value: string; onChange: (value: string) => void }

vi.mock('../components/controls/variable-input', () => ({
  VariableInput: ({ value, onChange }: StringControlProps) => (
    <button type="button" data-testid="tool-VariableInput" data-value={value} onClick={() => onChange('__variable_value__')}>变量输入</button>
  ),
}))
vi.mock('../components/controls/variable-name-input', () => ({
  VariableNameInput: ({ value, onChange }: StringControlProps) => (
    <button type="button" data-testid="tool-VariableNameInput" data-value={value} onClick={() => onChange('output_verified')}>变量名称</button>
  ),
}))
vi.mock('../components/controls/variable-ref-input', () => ({
  VariableRefInput: ({ value, onChange }: StringControlProps) => (
    <button type="button" data-testid="tool-VariableRefInput" data-value={value} onClick={() => onChange('reference_verified')}>变量引用</button>
  ),
}))
vi.mock('../components/controls/number-input', () => ({
  NumberInput: ({ value, onChange }: { value: number | string; onChange: (value: number | string) => void }) => (
    <button type="button" data-testid="tool-NumberInput" data-value={String(value)} onClick={() => onChange(37)}>数字输入</button>
  ),
}))

// These controls compose VariableInput or NumberInput internally. Removing them here keeps
// this suite scoped to direct panel consumers; their own request protocols have dedicated tests.
vi.mock('../components/controls/path-input', () => ({ PathInput: () => null }))
vi.mock('../components/controls/image-path-input', () => ({ ImagePathInput: () => null }))
vi.mock('../components/controls/coordinate-input', () => ({ CoordinateInput: () => null }))
vi.mock('../components/controls/dual-coordinate-input', () => ({ DualCoordinateInput: () => null }))

import { modelApi } from '../api'
import { excludedModuleTypes, moduleCategories } from '../lib/moduleCatalog'
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'

const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')
const tools = ['VariableInput', 'VariableNameInput', 'VariableRefInput', 'NumberInput'] as const
type Tool = (typeof tools)[number]
type ToolCase = { id: string; capability: string; preconditions: { tool: string } }
const entries = (toolCases.cases as ToolCase[])
  .filter(entry => tools.includes(entry.preconditions.tool as Tool))
  .map(entry => ({ id: entry.id, type: entry.capability.slice(5) as ModuleType, tool: entry.preconditions.tool as Tool, managedModel: false }))
  .flatMap(entry => entry.tool === 'VariableInput' && ['ai_generate_image', 'ai_generate_video'].includes(entry.type)
    ? [entry, { ...entry, id: `${entry.id}.managed-model`, managedModel: true }]
    : [entry])
const entrySetup: Record<string, Record<string, unknown>> = {
  'NODE.inject_javascript.tool.VariableInput': { injectMode: 'url_match' },
  'NODE.get_time.tool.VariableInput': { timeFormat: 'custom' },
  'NODE.list_operation.tool.VariableNameInput': { listAction: 'pop' },
  'NODE.ai_vision.tool.VariableRefInput': { imageSource: 'variable' },
  'NODE.webhook_request.tool.VariableNameInput': { saveResponse: true },
  'NODE.uuid_generator.tool.VariableInput': { uuidVersion: '5' },
}

beforeEach(() => store.getState().clearWorkflow())
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})

it.each(entries)('$id follows its current ConfigPanel consumer or explicit scope adaptation', async ({ id, type, tool, managedModel }) => {
  if (managedModel) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
  if (managedModel) vi.spyOn(modelApi, 'listOptions').mockResolvedValue({ success: true, data: {
    items: [{ id: 'model-test', providerId: 'provider-test', providerName: '托管供应商', modelKey: 'model', displayName: '主应用测试模型', tagsJson: [] }], total: 1,
  } })
  store.getState().addNode(type, { x: 0, y: 0 }, entrySetup[id])
  const nodeId = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={nodeId} />)
  const controls = screen.queryAllByTestId(`tool-${tool}`)
  if (excludedModuleTypes.has(type)) {
    expect(type.startsWith('notify_')).toBe(true)
    expect(moduleCategories.flatMap(category => category.modules)).not.toContain(type)
    expect(controls).toHaveLength(0)
    expect(screen.getAllByRole('status').map(element => element.textContent).join(' ')).toContain('此节点已排除，保留原配置，仅供查看和导出')
    expect(JSON.parse(store.getState().exportWorkflow()).nodes[0].data).toEqual(store.getState().nodes[0].data)
    return
  }

  const before = structuredClone(store.getState().nodes[0].data)
  if (managedModel) {
    // Prompt variable input and the approved managed-model selector coexist.
    expect(controls).toHaveLength(1)
    const picker = within(screen.getByText('主应用模型').parentElement!).getByRole('combobox')
    await waitFor(() => expect(picker.getAttribute('data-disabled')).toBeNull())
    fireEvent.keyDown(picker, { key: 'ArrowDown' })
    fireEvent.click(await screen.findByRole('option', { name: '主应用测试模型（托管供应商）' }))
    expect(store.getState().nodes[0].data.modelId).toBe('model-test')
    expect(store.getState().nodes[0].data.apiKey).toBeUndefined()
    expect(store.getState().nodes[0].data.apiBase).toBeUndefined()
  } else {
    expect(controls.length, `${id} did not mount a direct ${tool}`).toBeGreaterThan(0)
    fireEvent.click(controls[0])
  }
  const after = store.getState().nodes[0].data
  const changed = Object.keys({ ...before, ...after }).filter(key => !Object.is(before[key], after[key]))
  expect(changed, `${id} must write exactly one node field`).toHaveLength(1)

  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data).toEqual(before)
  act(() => store.getState().redo())
  expect(store.getState().nodes[0].data[changed[0]]).toEqual(after[changed[0]])

  const exported = store.getState().exportWorkflow()
  act(() => {
    store.getState().clearWorkflow()
    expect(store.getState().importWorkflow(exported)).toBe(true)
  })
  expect(store.getState().nodes.find(node => node.id === nodeId)!.data[changed[0]]).toEqual(after[changed[0]])
})
