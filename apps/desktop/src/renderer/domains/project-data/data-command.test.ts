import { expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import {
  createDataCommand,
  DataCommandNotAccepted,
  DataCommandUncertain,
} from './data-command'

const operation = {
  projectId: 'p',
  idempotencyKey: 'k',
  kind: 'deleteRecord' as const,
  status: 'succeeded' as const,
  resource: { type: 'record' as const },
  result: { deleted: true },
}

function client(request: StreamingApiClient['request']): StreamingApiClient {
  return { request, health: vi.fn(), stream: vi.fn() }
}

function command(request: StreamingApiClient['request']) {
  return createDataCommand(client(request), 'p')
}

it('projects a verified accepted response instead of returning its wrapper', async () => {
  const request = vi.fn().mockResolvedValue({ operation })

  await expect(command(request)(
    '/delete', 'DELETE', {}, 'k', 'deleteRecord', false,
    value => value.result,
    { acceptedResponse: true },
  )).resolves.toEqual({ deleted: true })
  expect(request).toHaveBeenCalledTimes(1)
})

it.each([
  {},
  { operation: { ...operation, projectId: 'other' } },
  { operation: { ...operation, idempotencyKey: 'wrong' } },
  { operation: { ...operation, kind: 'mutateRecord' } },
  { operation: { ...operation, status: 'accepted' } },
])('does not accept an incomplete or mismatched accepted operation', async accepted => {
  const request = vi.fn().mockResolvedValueOnce(accepted).mockResolvedValueOnce(accepted)

  await expect(command(request)(
    '/delete', 'DELETE', {}, 'k', 'deleteRecord', false,
    value => value.result,
    { acceptedResponse: true },
  )).rejects.toBeInstanceOf(DataCommandUncertain)
})

it.each([false, true])('lookup-only checks the original operation regardless of resume=%s', async resume => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))

  await expect(command(request)(
    '/delete', 'DELETE', {}, 'k', 'deleteRecord', resume,
    value => value.result,
    { lookupOnly: true },
  )).rejects.toBeInstanceOf(DataCommandNotAccepted)
  expect(request.mock.calls.map(call => call[0])).toEqual([
    '/api/v1/projects/p/operations/by-idempotency-key/k',
  ])
})

it('allows a read-only lookup of an already succeeded operation after write authority is revoked', async () => {
  const request = vi.fn().mockResolvedValue(operation)

  await expect(command(request)(
    '/delete', 'DELETE', {}, 'k', 'deleteRecord', false,
    value => value.result,
    { lookupOnly: true, canSubmit: () => false },
  )).resolves.toEqual({ deleted: true })
  expect(request).toHaveBeenCalledTimes(1)
})

it('rechecks write authority after lookup before resubmitting the original request', async () => {
  let canSubmit = true
  const request = vi.fn()
    .mockRejectedValueOnce(new TypeError('response lost'))
    .mockImplementationOnce(async () => {
      canSubmit = false
      throw new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND')
    })

  await expect(command(request)(
    '/delete', 'DELETE', {}, 'k', 'deleteRecord', false,
    value => value.result,
    { acceptedResponse: true, canSubmit: () => canSubmit },
  )).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(2)
})

it('does not issue the initial write when current authority is revoked', async () => {
  const request = vi.fn()

  await expect(command(request)(
    '/delete', 'DELETE', {}, 'k', 'deleteRecord', false,
    value => value.result,
    { acceptedResponse: true, canSubmit: () => false },
  )).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).not.toHaveBeenCalled()
})

it('keeps the default retry behavior and the original body snapshot', async () => {
  const body = { nested: { name: 'original' } }
  const request = vi.fn()
    .mockImplementationOnce(async () => {
      body.nested.name = 'changed'
      throw new TypeError('response lost')
    })
    .mockRejectedValueOnce(new ApiClientError('absent', 404, 'OPERATION_NOT_FOUND'))
    .mockResolvedValueOnce({ saved: true })

  await expect(command(request)(
    '/save', 'PATCH', body, 'k', 'updateRecord', false,
    value => value.result,
  )).resolves.toEqual({ saved: true })
  expect(request).toHaveBeenCalledTimes(3)
  expect(request.mock.calls[0][1].body).toEqual({ nested: { name: 'original' } })
  expect(request.mock.calls[2]).toEqual(request.mock.calls[0])
})

it('keeps a non-operation 404 lookup uncertain without resubmitting', async () => {
  const request = vi.fn().mockRejectedValueOnce(new ApiClientError('missing project', 404, 'PROJECT_NOT_FOUND'))

  await expect(command(request)(
    '/save', 'POST', {}, 'k', 'updateRecord', true,
    value => value.result,
  )).rejects.toBeInstanceOf(DataCommandUncertain)
  expect(request).toHaveBeenCalledTimes(1)
})

it.each([401, 403, 409, 410])('does not look up or retry a definitive %s write failure', async status => {
  const error = new ApiClientError('rejected', status, 'REJECTED')
  const request = vi.fn().mockRejectedValueOnce(error)

  await expect(command(request)(
    '/save', 'PUT', {}, 'k', 'updateRecord', false,
    value => value.result,
  )).rejects.toBe(error)
  expect(request).toHaveBeenCalledTimes(1)
})
