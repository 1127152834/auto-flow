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

it('offers signature references for bound fields and converts old references on request', async () => {
  // Remediation M2 R2-19/22.
  const { projectReferences } = await import('../project-inputs')
  const automation = useProjectInputs.getState().automation!
  expect(projectReferences(automation, [])[0].name).toBe(`PROJECT_INPUTS['i']['values']['f']`)
  const bound = { ...automation, inputPlan: { inputs: automation.inputPlan.inputs.map(input => ({ ...input, signatureInput: 'account', fieldBindings: input.fieldBindings.map(binding => ({ ...binding, signatureField: 'email' })) })) } }
  expect(projectReferences(bound, [])[0].name).toBe('input.account.email')
  const original = useProjectInputs.getState().convertToSignature
  const convertToSignature = vi.fn(async () => undefined)
  useProjectInputs.setState({ convertToSignature })
  render(<ProjectInputPanel />)
  fireEvent.click(screen.getByRole('button', { name: '转换为流程输入' }))
  expect(convertToSignature).toHaveBeenCalledOnce()
  cleanup()
  useProjectInputs.setState({ automation: bound as never })
  render(<ProjectInputPanel />)
  expect(screen.queryByRole('button', { name: '转换为流程输入' })).toBeNull()
  useProjectInputs.setState({ convertToSignature: original })
})

it('does not convert while the workflow has unsaved changes', async () => {
  useWorkflowStore.setState({ hasUnsavedChanges: true })
  const { convertToSignature } = useProjectInputs.getState()
  await convertToSignature()
  expect(useProjectInputs.getState().error).toBe('请先保存工作流，再转换为流程输入')
  useWorkflowStore.setState({ hasUnsavedChanges: false })
})

const email = { ref: { fieldId: 'email' }, type: 'string', name: '邮箱' }
const candidate = (key: string, value: string) => ({ recordRef: { recordKey: { value: key } }, values: [{ fieldId: 'email', fieldName: '邮箱', value }], selectable: true, selection: { recordRef: { recordKey: { value: key } } } })
async function openPicker(identity: unknown, items: unknown[]) {
  useProjectInputs.setState({ fields: [email] as never, tables: [{ tableId: 't', name: '账号表', identity }] as never, candidates: vi.fn().mockResolvedValue({ items, nextCursor: null }) })
  render(<ProjectInputPanel />)
  fireEvent.click(screen.getByRole('button', { name: '调试输入' }))
  fireEvent.click(screen.getByRole('button', { name: '选择数据' }))
  return screen.findByRole('dialog')
}

it('says the project data is only previewed by default and names the real-write switch honestly', () => {
  render(<ProjectInputPanel />)
  const box = screen.getByRole('checkbox', { name: '运行一次时真实写入项目数据' }) as HTMLInputElement
  expect(box.checked).toBe(false)
  expect(screen.getByText('项目数据仅预览，网页操作仍真实执行')).toBeDefined()
  expect(screen.queryByText(/修改会保存到项目数据/)).toBeNull()
  fireEvent.click(box)
  expect(useProjectInputs.getState().realWrites).toBe(true)
  expect(screen.getByText(/会改动项目数据/, { selector: 'p' })).toBeDefined()
  expect(screen.queryByText('项目数据仅预览，网页操作仍真实执行')).toBeNull()
  useProjectInputs.setState({ realWrites: false })
})

it('names candidate rows by the table display field and never shows the record key', async () => {
  const dialog = await openPicker({ mode: 'field', fieldId: 'email' }, [candidate('KEY-001', 'first@example.test'), candidate('KEY-002', 'second@example.test')])
  expect(await screen.findByRole('radio', { name: '选择记录 first@example.test' })).toBeDefined()
  expect(dialog.textContent).not.toMatch(/KEY-00/)
  const { findInternalIds } = await import('../../../shared/testing/internal-id-scan')
  expect(findInternalIds(dialog)).toEqual([])
})

it('falls back to the row number when the table has no display field in its values', async () => {
  const dialog = await openPicker({ mode: 'system' }, [candidate('KEY-001', 'first@example.test'), candidate('KEY-002', 'second@example.test')])
  expect(await screen.findByRole('radio', { name: '选择记录 第 2 行' })).toBeDefined()
  expect(dialog.textContent).not.toMatch(/KEY-00/)
})

it('does not show the record key for the chosen debug record either', () => {
  useProjectInputs.setState({ fields: [email] as never, tables: [{ tableId: 't', name: '账号表', identity: { mode: 'field', fieldId: 'email' } }] as never })
  render(<ProjectInputPanel />)
  fireEvent.click(screen.getByRole('button', { name: '调试输入' }))
  expect(screen.queryByText(/A-003/)).toBeNull()
  expect(screen.getByText(/记录：third@example.test/)).toBeDefined()
})
