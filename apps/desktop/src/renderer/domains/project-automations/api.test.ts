import { expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { createAutomationApi, AutomationCommandUncertain } from './api'
import type { AutomationWrite } from './types'

const body: AutomationWrite = {
  workflowId: 'w', name: '配置', description: '', inputPlan: { inputs: [] }, parameterSchema: [],
  environmentPolicy: { source: 'newFromProfile' },
  runPolicy: { maxTasks: 1, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 3600 },
}
const automation = { ...body, automationId: 'a', projectId: 'p', managementRevision: 1 }
const operation = { projectId: 'p', idempotencyKey: 'key', kind: 'createAutomation', status: 'succeeded', resource: { type: 'automation', projectId: 'p', automationId: 'a' }, result: automation }
function client(request: StreamingApiClient['request']): StreamingApiClient { return { request, health: vi.fn(), stream: vi.fn() } }

it('recovers a committed creation response using the original operation without posting again', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('lost')).mockResolvedValueOnce(operation)
  await expect(createAutomationApi(client(request), 'p').create(body, 'key')).resolves.toEqual(automation)
  expect(request).toHaveBeenCalledTimes(2)
  expect(request.mock.calls[1][0]).toBe('/api/v1/projects/p/operations/by-idempotency-key/key')
})
it.each([
  { ...operation, projectId: 'other' },
  { ...operation, kind: 'updateAutomation' },
  { ...operation, resource: { ...operation.resource, automationId: 'other' } },
  { ...operation, result: { ...automation, workflowId: 'other' } },
])('rejects mismatched persisted identity', async wrong => {
  const request = vi.fn().mockResolvedValue(wrong)
  await expect(createAutomationApi(client(request), 'p').resumeCreate(body, 'key')).rejects.toBeInstanceOf(AutomationCommandUncertain)
  expect(request).toHaveBeenCalledOnce()
})
it('only resends the identical command after an explicit operation-not-found result', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('lost')).mockRejectedValueOnce(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND')).mockResolvedValueOnce(automation)
  await createAutomationApi(client(request), 'p').create(body, 'key')
  expect(request.mock.calls[2]).toEqual(request.mock.calls[0])
})
it('keeps conflicts intact and does not retry with another key', async () => {
  const conflict = new ApiClientError('modified', 409, 'REVISION_CONFLICT')
  const request = vi.fn().mockRejectedValue(conflict)
  await expect(createAutomationApi(client(request), 'p').update('a', { ...body, expectedManagementRevision: 1 }, 'key')).rejects.toBe(conflict)
  expect(request).toHaveBeenCalledOnce()
})
it('rejects a late success after its workspace or instance becomes obsolete', async () => {
  let current = true
  const request = vi.fn().mockImplementation(async () => { current = false; return automation })
  await expect(createAutomationApi(client(request), 'p').create(body, 'key', { canSubmit: () => current })).rejects.toBeInstanceOf(AutomationCommandUncertain)
})
it('retains read cancellation and encodes directory conditions', async () => {
  const request = vi.fn().mockResolvedValue({ items: [] })
  const signal = new AbortController().signal
  await createAutomationApi(client(request), 'p').list({ query: 'a&b', page: 2, pageSize: 50, sort: '-name' }, signal)
  expect(request).toHaveBeenCalledWith('/api/v1/projects/p/automations?q=a%26b&page=2&pageSize=50&sort=-name', { signal })
})
