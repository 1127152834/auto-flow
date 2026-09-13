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

it.each(['commit_version', 'hub_publish_workflow', 'start_screensaver', 'open_phone_mirror', 'close_phone_mirror', 'capture_screen_for_agent'])('does not dispatch removed service action %s', async action => {
  const result = await executeClientAction(action, {})
  expect(result.success).toBe(false)
  expect(result.error).toContain('未知 action')
})

it.each(['replace_module_type', 'update_node_config', 'bulk_update_nodes'])('blocks excluded types introduced through %s without partial edits', async action => {
  useWorkflowStore.getState().addNode('open_page', { x: 0, y: 0 })
  const before = structuredClone(useWorkflowStore.getState().nodes)
  const nodeId = before[0].id
  const result = await executeClientAction(action, {
    node_id: nodeId, new_type: 'excel_create', config: { moduleType: 'excel_create' },
    patches: [{ node_id: nodeId, config: { url: 'changed' } }, { node_id: nodeId, config: { moduleType: 'excel_create' } }],
  })
  expect(result.success).toBe(false)
  expect(useWorkflowStore.getState().nodes).toEqual(before)
})

it('replaces the business type without corrupting React Flow rendering or restoring stale data, and supports undo', async () => {
  useWorkflowStore.getState().addNode('open_page', { x: 120, y: 80 })
  const before = structuredClone(useWorkflowStore.getState().nodes)
  const result = await executeClientAction('replace_module_type', { node_id: before[0].id, new_type: 'click_element' })
  expect(result.success).toBe(true)
  expect(useWorkflowStore.getState().nodes[0]).toMatchObject({
    id: before[0].id, type: 'moduleNode', position: { x: 120, y: 80 }, data: { moduleType: 'click_element' },
  })
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  useWorkflowStore.getState().undo()
  expect(useWorkflowStore.getState().nodes).toEqual(before)
})
it('adds permitted nodes as one undoable edit without dropping existing variables', async () => {
  useWorkflowStore.getState().addVariable({ name: 'retained', type: 'string', value: 'keep', scope: 'global' })
  const variables = structuredClone(useWorkflowStore.getState().variables)
  const result = await executeClientAction('add_nodes', { nodes: [{ id: 'new-web', type: 'open_page' }] })
  expect(result.success).toBe(true)
  expect(useWorkflowStore.getState().variables).toEqual(variables)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  useWorkflowStore.getState().undo()
  expect(useWorkflowStore.getState().nodes).toEqual([])
  expect(useWorkflowStore.getState().variables).toEqual(variables)
  useWorkflowStore.getState().redo()
  expect(useWorkflowStore.getState().nodes[0].id).toBe('new-web')
  expect(useWorkflowStore.getState().variables).toEqual(variables)
})
