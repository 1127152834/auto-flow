import { beforeEach, expect, it, vi } from 'vitest'
vi.mock('../hooks/stores/aiPermissionStore', () => ({ actionNeedsApproval: () => false, requestApproval: async () => true }))
import { executeClientAction } from '../api/aiAssistantSkills'
import { useWorkflowStore } from '../editor-store'
beforeEach(() => useWorkflowStore.getState().clearWorkflow())
it('rejects excluded AI additions while preserving the current document', async () => {
  useWorkflowStore.getState().addNode('open_page', { x: 0, y: 0 })
  const before = useWorkflowStore.getState().nodes
  const result = await executeClientAction('add_nodes', { nodes: [{ id: 'excel', type: 'excel_create' }] })
  expect(result.success).toBe(false)
  expect(useWorkflowStore.getState().nodes).toEqual(before)
})
it('keeps permitted Web additions and removes edges referencing rejected nodes', async () => {
  const result = await executeClientAction('add_nodes', {
    nodes: [{ id: 'web', type: 'open_page' }, { id: 'bot', type: 'qq_send_message' }],
    edges: [{ id: 'edge', source: 'web', target: 'bot' }],
  })
  expect(result.success).toBe(true)
  expect(useWorkflowStore.getState().nodes.map(node => node.id)).toEqual(['web'])
  expect(useWorkflowStore.getState().edges).toEqual([])
})

it.each(['upload_excel', 'list_data_assets', 'preview_data_asset'])('rejects removed Excel tool %s without a service request', async action => {
  const result = await executeClientAction(action, {})
  expect(result.success).toBe(false)
  expect(result.error).toContain('已从 AutoFlow Studio 移除')
})
it('rejects AI attempts to reopen the removed Excel panel', async () => {
  const previous = useWorkflowStore.getState().bottomPanelTab
  expect((await executeClientAction('switch_bottom_panel', { tab: 'assets' })).success).toBe(false)
  expect(useWorkflowStore.getState().bottomPanelTab).toBe(previous)
})
