import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { StudioApp } from './StudioApp'

const mocks = vi.hoisted(() => ({
  get: vi.fn(), importWorkflow: vi.fn(), workflowId: 'workflow',
}))
vi.mock('../domains/workflows/api', () => ({ workflowApi: { get: mocks.get } }))
vi.mock('../domains/workflows/api/config', () => ({ getStudioOpenContext: () => ({ workflowId: mocks.workflowId }) }))
vi.mock('../domains/workflows/editor-store', () => ({ useWorkflowStore: { getState: () => ({ importWorkflow: mocks.importWorkflow, hasUnsavedChanges: false }) } }))
vi.mock('../domains/workflows/hooks/useStudioIntegration', () => ({ useStudioIntegration: () => {} }))
vi.mock('../domains/workflows/hooks/stores/aiAssistantStore', () => ({ useAIAssistantStore: (select: (value: { isPanelOpen: boolean }) => unknown) => select({ isPanelOpen: false }) }))
vi.mock('../domains/workflows/hooks/stores/layoutStore', () => ({ useLayoutStore: (select: (value: { aiAssistantWidth: number }) => unknown) => select({ aiAssistantWidth: 0 }) }))
vi.mock('../domains/workflows/lib/documentLeave', () => ({ requestDocumentLeave: async () => true, getDocumentLeaveResources: () => [] }))
vi.mock('../domains/workflows/lib/settingsLeave', () => ({ hasSettingsCloseHandler: () => false, requestSettingsClose: async () => true }))
vi.mock('../domains/workflows/components/WorkflowEditor', () => ({ WorkflowEditor: () => <button>编辑画布</button> }))
vi.mock('../domains/workflows/components/StudioConnectionNotice', () => ({ StudioConnectionNotice: () => null }))
vi.mock('../domains/workflows/components/assistant/AIAssistantPanel', () => ({ AIAssistantPanel: () => null }))
vi.mock('../domains/workflows/components/InputPromptDialog', () => ({ InputPromptDialog: () => null }))

type Response = { success: boolean; data?: { id: string; name?: string }; error?: string }
function pending() {
  let resolve!: (value: Response) => void
  const promise = new Promise<Response>(done => { resolve = done })
  return { promise, resolve }
}
beforeEach(() => {
  mocks.get.mockReset()
  mocks.importWorkflow.mockReset().mockReturnValue(true)
  mocks.workflowId = 'workflow'
})
afterEach(cleanup)

it('locks editing until the project document has loaded', async () => {
  const request = pending()
  mocks.get.mockReturnValue(request.promise)
  render(<StudioApp />)
  expect(screen.queryByRole('button', { name: '编辑画布' })).not.toBeInTheDocument()
  expect(screen.getByRole('status')).toHaveTextContent('正在读取项目工作流')
  await act(async () => request.resolve({ success: true, data: { id: 'workflow' } }))
  expect(await screen.findByRole('button', { name: '编辑画布' })).toBeEnabled()
  expect(mocks.importWorkflow).toHaveBeenCalledExactlyOnceWith({ id: 'workflow' })
})

it('keeps failed loading locked and offers an explicit retry', async () => {
  mocks.get.mockResolvedValueOnce({ success: false, error: '服务离线' }).mockResolvedValueOnce({ success: true, data: { id: 'workflow' } })
  render(<StudioApp />)
  expect(await screen.findByRole('alert')).toHaveTextContent('服务离线')
  expect(screen.queryByRole('button', { name: '编辑画布' })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '重新读取' }))
  expect(await screen.findByRole('button', { name: '编辑画布' })).toBeEnabled()
  expect(mocks.get).toHaveBeenCalledTimes(2)
})

it('ignores a response from the connection preceding a reconnect', async () => {
  const old = pending(), current = pending()
  mocks.get.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
  render(<StudioApp />)
  act(() => window.dispatchEvent(new Event('studio:transport-changed')))
  await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2))
  await act(async () => current.resolve({ success: true, data: { id: 'workflow', name: 'current' } }))
  await act(async () => old.resolve({ success: true, data: { id: 'workflow', name: 'stale' } }))
  expect(mocks.importWorkflow).toHaveBeenCalledExactlyOnceWith({ id: 'workflow', name: 'current' })
})

it('does not reload an edited document after same-workspace reconnect', async () => {
  mocks.get.mockResolvedValue({ success: true, data: { id: 'workflow' } })
  render(<StudioApp />)
  await screen.findByRole('button', { name: '编辑画布' })
  await waitFor(() => expect(mocks.importWorkflow).toHaveBeenCalledOnce())
  act(() => window.dispatchEvent(new Event('studio:transport-changed')))
  expect(mocks.get).toHaveBeenCalledOnce()
})

it('does not import a document returned for another identity', async () => {
  mocks.get.mockResolvedValue({ success: true, data: { id: 'another-workflow' } })
  render(<StudioApp />)
  expect(await screen.findByRole('alert')).toHaveTextContent('无法读取项目工作流')
  expect(mocks.importWorkflow).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: '编辑画布' })).not.toBeInTheDocument()
})

it('handles a rejected request and ignores a result after unmount', async () => {
  const request = pending()
  mocks.get.mockRejectedValueOnce(new Error('network')).mockReturnValueOnce(request.promise)
  const view = render(<StudioApp />)
  expect(await screen.findByRole('alert')).toHaveTextContent('请检查服务连接后重试')
  await userEvent.click(screen.getByRole('button', { name: '重新读取' }))
  view.unmount()
  await act(async () => request.resolve({ success: true, data: { id: 'workflow' } }))
  expect(mocks.importWorkflow).not.toHaveBeenCalled()
})
