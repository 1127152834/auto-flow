import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
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

import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'

const tools = ['VariableInput', 'VariableNameInput', 'VariableRefInput', 'NumberInput'] as const
type Tool = (typeof tools)[number]
type ToolCase = { id: string; capability: string; preconditions: { tool: string } }
const entries = (toolCases.cases as ToolCase[])
  .filter(entry => tools.includes(entry.preconditions.tool as Tool))
  .map(entry => ({ id: entry.id, type: entry.capability.slice(5) as ModuleType, tool: entry.preconditions.tool as Tool }))
const entrySetup: Record<string, Record<string, unknown>> = {
  'NODE.inject_javascript.tool.VariableInput': { injectMode: 'url_match' },
  'NODE.get_time.tool.VariableInput': { timeFormat: 'custom' },
  'NODE.list_operation.tool.VariableNameInput': { listAction: 'pop' },
  'NODE.ai_vision.tool.VariableRefInput': { imageSource: 'variable' },
  'NODE.webhook_request.tool.VariableNameInput': { saveResponse: true },
  'NODE.uuid_generator.tool.VariableInput': { uuidVersion: '5' },
}

beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)

it.each(entries)('$id mounts and commits through its actual ConfigPanel consumer', ({ id, type, tool }) => {
  store.getState().addNode(type, { x: 0, y: 0 }, entrySetup[id])
  const nodeId = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={nodeId} />)
  const controls = screen.queryAllByTestId(`tool-${tool}`)
  expect(controls.length, `${id} did not mount a direct ${tool}`).toBeGreaterThan(0)

  const before = structuredClone(store.getState().nodes[0].data)
  fireEvent.click(controls[0])
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
