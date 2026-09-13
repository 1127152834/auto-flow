import { beforeEach, expect, it } from 'vitest'
import { moduleCategories } from '../components/ModuleSidebar'
import { useWorkflowStore } from '../editor-store'
const types = moduleCategories.flatMap(category => category.modules)
beforeEach(() => useWorkflowStore.getState().clearWorkflow())
it.each(types)('NODE.%s.roundtrip: preserves created configuration through export/import', type => {
  useWorkflowStore.getState().addNode(type, { x: 120, y: 240 })
  const created = structuredClone(useWorkflowStore.getState().nodes)
  expect(created.length).toBeGreaterThan(0)
  expect(created.some(node => node.data.moduleType === type)).toBe(true)
  const content = useWorkflowStore.getState().exportWorkflow()
  useWorkflowStore.getState().clearWorkflow()
  expect(useWorkflowStore.getState().importWorkflow(content)).toBe(true)
  const restored = useWorkflowStore.getState().nodes
  for (const node of created) {
    expect(restored.find(item => item.id === node.id)).toMatchObject({ id: node.id, data: node.data, position: node.position })
  }
})
