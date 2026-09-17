import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type ApiRequestInit, type StreamingApiClient } from '../../../shared/api/client'
import type { Automation } from '../../project-automations/types'
import { BatchLauncher, type BatchLauncherProps } from './BatchLauncher'

const stored = new Map<string, string>()
beforeEach(() => { vi.stubGlobal('localStorage', { getItem: (key: string) => stored.get(key) ?? null, setItem: (key: string, value: string) => stored.set(key, value), removeItem: (key: string) => stored.delete(key) }); vi.stubGlobal('crypto', { randomUUID: () => 'command-key' }) })
afterEach(() => { cleanup(); stored.clear(); vi.unstubAllGlobals() })
const automation: Automation = { automationId: 'a', projectId: 'p', workflowId: 'wf', name: '资料整理', description: '', managementRevision: 7, inputPlan: { inputs: [] }, parameterSchema: [], environmentPolicy: { source: 'newFromProfile', profileId: 'profile', proxyOverride: { mode: 'fixed', proxyId: 'proxy' }, modelProviderId: 'model' }, runPolicy: { maxTasks: 10, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 900 }, createdAt: '', updatedAt: '' }
function props(request: StreamingApiClient['request'], override: Partial<BatchLauncherProps> = {}): BatchLauncherProps { return { open: true, onOpenChange: vi.fn(), savedAutomation: automation, validation: { status: 'ready', valid: true, runnable: true, issues: [], capabilityRequirements: [], checkedAt: '' }, onRefreshValidation: vi.fn(), workspaceKey: 'w', instanceId: 'i', projectId: 'p', client: { request, stream: vi.fn(), health: vi.fn() }, disabled: false, readOnly: false, onBatchCreated: vi.fn(), resourceSummary: [], ...override } }
it('keeps the controlled launch draft across close, instance reconnect, and revision refresh', () => {
  const p = props(vi.fn()); const view = render(<BatchLauncher {...p}/>)
  fireEvent.change(screen.getByLabelText('本次任务数'), { target: { value: '23' } })
  view.rerender(<BatchLauncher {...p} open={false} instanceId="i2" savedAutomation={{ ...automation, managementRevision: 8 }}/>)
  view.rerender(<BatchLauncher {...p} open instanceId="i2" savedAutomation={{ ...automation, managementRevision: 8 }}/>)
  expect(screen.getByLabelText('本次任务数')).toHaveValue('23')
})
it('preserves saved resource references in the temporary environment override and navigates accepted batches', async () => {
  const writes: ApiRequestInit[] = [], request = vi.fn(async (_path: string, init?: ApiRequestInit) => { writes.push(init!); return { operation: { operationId: 'op', projectId: 'p', idempotencyKey: 'command-key', kind: 'startBatch', status: 'accepted', statusRevision: 1, resource: { type: 'batch', projectId: 'p', batchId: 'b' }, result: null, error: null, inputs: [], capturedAt: '' } } }) as StreamingApiClient['request']
  const p = props(request); render(<BatchLauncher {...p}/>)
  fireEvent.click(screen.getByRole('radio', { name: '每个任务创建临时环境' })); fireEvent.click(screen.getByRole('button', { name: '启动 10 个任务' }))
  await waitFor(() => expect(p.onBatchCreated).toHaveBeenCalledWith('b'))
  expect(writes[0].body).toMatchObject({ environmentOverride: { source: 'newFromProfile', profileId: 'profile', proxyOverride: { mode: 'fixed', proxyId: 'proxy' }, modelProviderId: 'model' } })
  await waitFor(() => expect(stored.size).toBe(0))
  fireEvent.click(screen.getByRole('button', { name: '启动 10 个任务' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
})
it('shows validation issue reasons and does not label an ordinary rejection as damaged recovery data', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('参数冲突', 422, 'VALIDATION_FAILED')) as StreamingApiClient['request']
  const p = props(request, { validation: { status: 'blocked', valid: true, runnable: false, issues: [{ code: 'PROFILE_NOT_FOUND', message: 'profile 123e4567-e89b-42d3-a456-426614174000 is unavailable', path: ['environmentPolicy', 'profileId'] }], capabilityRequirements: [], checkedAt: '' } })
  const view = render(<BatchLauncher {...p}/>)
  expect(screen.getByText('浏览器配置暂不可用，请重新选择')).toBeVisible()
  expect(document.body.textContent).not.toContain('123e4567-e89b-42d3-a456-426614174000')
  view.rerender(<BatchLauncher {...p} validation={{ status: 'ready', valid: true, runnable: true, issues: [], capabilityRequirements: [], checkedAt: '' }}/>)
  fireEvent.click(screen.getByRole('button', { name: '启动 10 个任务' }))
  await waitFor(() => expect(screen.getAllByRole('alert').some(item => item.textContent?.includes('输入内容不符合要求'))).toBe(true))
  expect(screen.queryByRole('button', { name: '清除损坏的恢复资料' })).not.toBeInTheDocument()
})
it('keeps the original operation identity locked when the network outcome is unknown', async () => {
  const request = vi.fn().mockRejectedValue(new Error('网络中断')) as StreamingApiClient['request']
  render(<BatchLauncher {...props(request)}/>)
  fireEvent.click(screen.getByRole('button', { name: '启动 10 个任务' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '核对原操作' })).toBeVisible())
  expect([...stored.values()][0]).toContain('command-key')
  expect(screen.queryByRole('button', { name: '清除损坏的恢复资料' })).not.toBeInTheDocument()
})
it('does not consume a stop recovery envelope from the same project', () => {
  const foreignKey = 'autoflow:project-run-command:["w","p"]'
  stored.set(foreignKey, JSON.stringify({ type: 'stop', batchId: 'batch-other', body: { expectedStatusRevision: 1, reason: '停止' }, key: 'stop-key' }))
  const p = props(vi.fn())
  render(<BatchLauncher {...p}/>)
  expect(screen.queryByRole('button', { name: '核对原操作' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '启动 10 个任务' })).toBeEnabled()
  expect(stored.get(foreignKey)).toContain('stop-key')
  expect(p.onBatchCreated).not.toHaveBeenCalled()
})
it.each(['temporarilyBusy', 'noMatch'])('allows accepting a data batch after a valid %s preview', async selectionStatus => {
  const request = vi.fn().mockResolvedValue({ runnable: false, selectionStatus, inputs: [], capturedAt: '' }) as StreamingApiClient['request']
  render(<BatchLauncher {...props(request, { savedAutomation: { ...automation, inputPlan: { inputs: [{ inputId: 'input', alias: '资料', tableId: 'table', datasetGeneration: 'generation', mode: 'independent', required: true, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [] }] } } })}/>)
  await waitFor(() => expect(request).toHaveBeenCalled())
  await waitFor(() => expect(screen.getByRole('button', { name: '启动 10 个任务' })).toBeEnabled())
})
it('offers unlimited only with required inputs and sends an explicit null with requested concurrency', async () => {
  const request = vi.fn().mockResolvedValue({ runnable: true, selectionStatus: 'ready', inputs: [], capturedAt: '' }) as StreamingApiClient['request']
  render(<BatchLauncher {...props(request, { savedAutomation: { ...automation, inputPlan: { inputs: [{ inputId: 'input', alias: '资料', tableId: 'table', datasetGeneration: 'generation', mode: 'independent', required: true, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [] }] } } })}/>)
  await waitFor(() => expect(screen.getByRole('button', { name: '启动 10 个任务' })).toBeEnabled())
  fireEvent.click(screen.getByRole('radio', { name: '不限次数' }))
  fireEvent.change(screen.getByLabelText('请求并发数'), { target: { value: '2' } })
  fireEvent.click(screen.getByRole('button', { name: '启动不限次数批次' }))
  await waitFor(() => expect(request).toHaveBeenCalledWith(expect.stringContaining('/batches'), expect.objectContaining({ body: expect.objectContaining({ maxTasks: null, concurrency: 2 }) })))
})
it('keeps parameter-only batches finite and explains the frozen failure policy', () => {
  render(<BatchLauncher {...props(vi.fn())}/>)
  expect(screen.queryByRole('radio', { name: '不限次数' })).not.toBeInTheDocument()
  expect(screen.getByText(/首次确认失败后停止执行后续排队任务/)).toBeVisible()
})

it.each(['configurationError', 'scanBudgetExceeded', 'ambiguous'])('keeps %s preview blocked', async selectionStatus => {
  const request = vi.fn().mockResolvedValue({ runnable: false, selectionStatus, inputs: [], capturedAt: '' }) as StreamingApiClient['request']
  render(<BatchLauncher {...props(request, { savedAutomation: { ...automation, inputPlan: { inputs: [{ inputId: 'input', alias: '资料', tableId: 'table', datasetGeneration: 'generation', mode: 'independent', required: false, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [] }] } } })}/>)
  await waitFor(() => expect(screen.getByText('当前不能领取完整输入组')).toBeVisible())
  expect(screen.getByRole('button', { name: '启动 10 个任务' })).toBeDisabled()
  expect(screen.queryByRole('radio', { name: '不限次数' })).not.toBeInTheDocument()
})
it('forces legacy parameter-only automations to a disabled concurrency of one', () => {
  render(<BatchLauncher {...props(vi.fn(), { savedAutomation: { ...automation, runPolicy: { ...automation.runPolicy, concurrency: 3 } } })}/>)
  expect(screen.getByLabelText('请求并发数')).toHaveValue('1')
  expect(screen.getByLabelText('请求并发数')).toBeDisabled()
  expect(screen.getByText('参数型自动化按顺序执行，并发数固定为 1')).toBeVisible()
})
