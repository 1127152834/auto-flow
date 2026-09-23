import { afterEach, beforeEach, expect, it } from 'vitest'
import capabilities from '../../../../../../../docs/migration/studio-frontend-completion/capabilities.json'
import componentTools from '../../../../../../../docs/migration/studio-frontend-completion/component-tools.json'
import fieldCases from '../../../../../../../docs/migration/studio-frontend-completion/evidence/f2-node-fields/cases.json'
import reconciliation from '../../../../../../../docs/migration/studio-frontend-completion/evidence/f2-node-reconcile/reconciliation.json'
import { useWorkflowStore as store } from '../editor-store'
import { excludedModuleTypes } from '../lib/moduleCatalog'
import type { ModuleType } from '../types/workflow'

type Capability = { id: string; type: ModuleType }
type FieldCase = { id: string; capability: string; preconditions?: { field?: string } }
type ReconciledComponent = { component: string; file: string }
type ReconciledNode = { capabilityId: string; specializedFields: string[]; sourceComponents: ReconciledComponent[] }
type CurrentComponent = { component: string; file: string; fields: string[] }

const reconciliationById = new Map(
  (reconciliation.nodes as ReconciledNode[]).map(node => [node.capabilityId, node]),
)
const currentComponents = componentTools as CurrentComponent[]
const explicitInlineFields = new Map<string, string>([
  ['NODE.element_exists.field.leftValue', 'selector-entry-wiring.test.tsx'],
  ['NODE.element_visible.field.leftValue', 'selector-entry-wiring.test.tsx'],
  ['NODE.stop_workflow.field.stopReason', 'web-config-text.test.tsx'],
  ['NODE.ai_route.field.moduleType', 'catalog-panel-registration.test.tsx'],
  ['NODE.note.field.content', 'complex-structure-interactions.test.tsx'],
])

const capabilityById = new Map((capabilities as Capability[]).map(capability => [capability.id, capability]))
const fieldEntries = (fieldCases as FieldCase[])
  .filter(testCase => testCase.id.includes('.field.') && testCase.preconditions?.field)
const excludedEntries = fieldEntries.filter(testCase => !capabilityById.has(testCase.capability))
const entries = fieldEntries
  .filter(testCase => capabilityById.has(testCase.capability))
  .map(testCase => ({
    id: testCase.id,
    capabilityId: testCase.capability,
    type: capabilityById.get(testCase.capability)!.type,
    field: testCase.preconditions!.field!,
  }))

beforeEach(() => store.getState().clearWorkflow())
afterEach(() => store.getState().clearWorkflow())

it('historical field cases outside the current catalog belong only to the 14 excluded notification nodes', () => {
  const missingTypes = new Set(excludedEntries.map(testCase => testCase.capability.replace(/^node:/, '')))
  expect(missingTypes.size).toBe(14)
  for (const type of missingTypes) {
    expect(type.startsWith('notify_')).toBe(true)
    expect(excludedModuleTypes.has(type as ModuleType)).toBe(true)
  }
})

it.each(entries)('$id remains mapped by the current panel inventory and document contract', ({ id, capabilityId, type, field }) => {
  const reconciled = reconciliationById.get(capabilityId)
  expect(reconciled?.specializedFields, `${id} is absent from the frozen node mapping`).toContain(field)

  const mappedByCurrentPanel = reconciled?.sourceComponents.some(source =>
    currentComponents.some(current =>
      current.component === source.component && current.file === source.file && current.fields.includes(field),
    ),
  )
  expect(
    mappedByCurrentPanel || explicitInlineFields.has(id),
    `${id} is no longer present in the current component inventory and has no inline-entry evidence`,
  ).toBe(true)

  store.getState().addNode(type, { x: 0, y: 0 })
  const nodeId = store.getState().nodes[0].id
  if (field === 'moduleType') {
    expect(store.getState().nodes[0].data.moduleType).toBe(type)
  } else {
    const marker = `__field_contract__${type}__${field}`
    store.getState().updateNodeData(nodeId, { [field]: marker })
    expect(store.getState().nodes[0].data[field]).toBe(marker)
  }

  const document = store.getState().exportWorkflow()
  store.getState().clearWorkflow()
  expect(store.getState().importWorkflow(document)).toBe(true)
  const restored = store.getState().nodes.find(node => node.id === nodeId)
  expect(restored).toBeDefined()
  expect(restored!.data[field]).toEqual(field === 'moduleType' ? type : `__field_contract__${type}__${field}`)
})
