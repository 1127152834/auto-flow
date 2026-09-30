import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ProjectInputPanel } from '../components/ProjectInputPanel'
import { useWorkflowStore } from '../editor-store'
import { captureProjectReferenceTypes, useProjectInputs } from '../project-inputs'
afterEach(cleanup)
beforeEach(() => {
  useProjectInputs.setState({ automation: { automationId: 'a', projectId: 'p', workflowId: 'w', name: '注册', inputPlan: { inputs: [{ inputId: 'i', alias: '账号', tableId: 't', datasetGeneration: 'g', mode: 'independent', required: true, fieldBindings: [{ inputFieldId: 'f', inputFieldAlias: '邮箱', fieldRef: { fieldId: 'email' } }], filter: {}, orderBy: [] }] }, parameterSchema: [] } as never, debug: { selectionStatus: 'ready', selection: {}, inputs: [{ inputId: 'i', recordRef: { recordKey: { value: 'A-003' } }, values: [{ fieldId: 'email', value: 'third@example.test' }] }], items: [], nextCursor: null }, busy: false, candidates: vi.fn().mockResolvedValue({ items: [], nextCursor: null }), fields: [], task: null, taskDefinition: null, error: null, notice: null })
})
it('shows one object and opens a separate single-record picker', async () => {
  const candidates = vi.fn().mockResolvedValue({ items: [], nextCursor: null })
  useProjectInputs.setState({ candidates })
  render(<ProjectInputPanel />)
  fireEvent.click(screen.getByRole('button', { name: '调试输入' }))
  expect(screen.getByText('third@example.test')).toBeDefined()
  fireEvent.click(screen.getByRole('button', { name: '选择数据' }))
  expect(await screen.findByRole('dialog')).toBeDefined()
  expect(candidates).toHaveBeenCalledWith('i', null, '')
})

it('captures pasted references on the containing node and preserves the original expected type', () => {
  const automation = useProjectInputs.getState().automation!
  useProjectInputs.setState({ fields: [{ ref: { fieldId: 'email' }, type: 'string' }] as never })
  const reference = `PROJECT_INPUTS['i']['values']['f']`
  useWorkflowStore.setState({ selectedNodeId: 'other', nodes: [{ id: 'target', data: { variableValue: `{${reference}}` }, position: { x: 0, y: 0 } }, { id: 'other', data: {}, position: { x: 1, y: 1 } }] as never })
  captureProjectReferenceTypes()
  expect(useWorkflowStore.getState().nodes[0].data.projectInputTypes).toEqual({ [reference]: 'string' })
  expect(useWorkflowStore.getState().nodes[1].data.projectInputTypes).toBeUndefined()
  useProjectInputs.setState({ automation: { ...automation, inputPlan: { inputs: automation.inputPlan.inputs.map(input => ({ ...input, alias: '改名后' })) } }, fields: [{ ref: { fieldId: 'email' }, type: 'number' }] as never })
  captureProjectReferenceTypes()
  expect(useWorkflowStore.getState().nodes[0].data.projectInputTypes).toEqual({ [reference]: 'string' })
})

it('keeps the task input after its live definition is removed', () => {
  const automation = useProjectInputs.getState().automation!
  useProjectInputs.setState({ taskDefinition: { inputPlan: automation.inputPlan, parameterSchema: [] }, automation: { ...automation, inputPlan: { inputs: [] } }, task: { task: { taskOrdinal: 1, status: 'succeeded' }, inputSnapshot: { inputs: [{ inputId: 'i', values: [{ fieldId: 'email', value: 'frozen@example.test' }] }], parameters: {} }, dataWrites: [] } as never })
  render(<ProjectInputPanel />)
  fireEvent.click(screen.getByRole('button', { name: '本次任务' }))
  expect(screen.getByText('frozen@example.test')).toBeDefined()
})
