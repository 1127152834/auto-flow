import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { FailedRunFollowup } from './FailedRunFollowup'

afterEach(cleanup)

const client = (request: StreamingApiClient['request']): StreamingApiClient => ({ request, stream: vi.fn(), health: vi.fn() })
const batch = { batchId: 'b2', projectId: 'p', automationId: 'a' }
const operation = { operationId: 'op', projectId: 'p', idempotencyKey: '', kind: 'followUpBatch', status: 'succeeded', statusRevision: 2, resource: { type: 'batch', projectId: 'p', batchId: 'b2' }, result: { batch }, error: null, inputs: [], capturedAt: '' }
const props = { workspaceKey: 'ws', instanceId: 'i', projectId: 'p', taskId: 't1', statusRevision: 3, disabled: false }
type Init = { method?: string; headers: Record<string, string>; body: unknown }
const isLookup = (path: string) => path.includes('/operations/by-idempotency-key/')
const echo = (overrides: Partial<typeof operation> = {}) => vi.fn().mockImplementation((path: string, init: Init) => {
  const key = isLookup(path) ? decodeURIComponent(path.split('/').pop() ?? '') : init.headers['Idempotency-Key']
  const value = { ...operation, idempotencyKey: key, ...overrides }
  return Promise.resolve(isLookup(path) ? value : { operation: value })
})

it('submits nothing until the second confirmation is accepted', async () => {
  const request = echo(), onOpenBatch = vi.fn()
  render(<FailedRunFollowup {...props} client={client(request)} onOpenBatch={onOpenBatch}/>)
  fireEvent.click(screen.getByRole('button', { name: '以此输入重新运行' }))
  expect(await screen.findByText('从原输入组重新运行？')).toBeInTheDocument()
  expect(request).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '确认重新运行' }))
  await waitFor(() => expect(onOpenBatch).toHaveBeenCalledWith('b2'))
  expect(request.mock.calls[0][0]).toBe('/api/v1/projects/p/tasks/t1/follow-up-batches')
  expect(request.mock.calls[0][1].headers['Idempotency-Key']).toBeTruthy()
})

it('keeps the draft dialog and reports a real rejection without inventing a batch', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('conflict', 409, 'FOLLOW_UP_NOT_ALLOWED')), onOpenBatch = vi.fn()
  render(<FailedRunFollowup {...props} client={client(request)} onOpenBatch={onOpenBatch}/>)
  fireEvent.click(screen.getByRole('button', { name: '以此输入重新运行' }))
  fireEvent.click(screen.getByRole('button', { name: '确认重新运行' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('数据已发生变化，请刷新后重试')
  expect(onOpenBatch).not.toHaveBeenCalled()
  expect(request).toHaveBeenCalledTimes(1)
})

it('reuses the original key for the follow-up lookup instead of minting a new one', async () => {
  const request = echo().mockRejectedValueOnce(new TypeError('offline')).mockRejectedValueOnce(new TypeError('offline')), onOpenBatch = vi.fn()
  render(<FailedRunFollowup {...props} client={client(request)} onOpenBatch={onOpenBatch}/>)
  fireEvent.click(screen.getByRole('button', { name: '以此输入重新运行' }))
  fireEvent.click(screen.getByRole('button', { name: '确认重新运行' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('结果尚未确认，请按原操作身份核对。')
  const submitted = request.mock.calls[0][1].headers['Idempotency-Key']
  fireEvent.click(screen.getByRole('button', { name: '核对原操作' }))
  await waitFor(() => expect(onOpenBatch).toHaveBeenCalledWith('b2'))
  expect(request.mock.calls[2][0]).toContain(`/operations/by-idempotency-key/${submitted}`)
})
