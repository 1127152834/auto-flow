import { describe, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../shared/api/client'
import { createStatusBatchApi } from './status-batch-api'

const operation = { projectId: 'p', idempotencyKey: 'start-key', kind: 'setRecordStatuses', operationId: 'op', status: 'accepted', statusRevision: 1, resource: { type: 'table', projectId: 'p', tableId: 't' } }

describe('status batch api', () => {
  it('previews and durably accepts the frozen request', async () => {
    const request = vi.fn(async (path: string, _init?: unknown) => path.endsWith('/preview') ? { blocks: [] } : { operation })
    const api = createStatusBatchApi({ request } as unknown as StreamingApiClient, 'p', 't')
    const body = { statusId: null, targets: [], blockSize: 100 }
    await api.preview(body)
    await expect(api.start(body, 'start-key', () => true)).resolves.toMatchObject({ status: 'accepted' })
    expect(request.mock.calls[0][0]).toContain('/record-status-batches/preview')
  })

  it('looks up the original key and cancels with a distinct command key', async () => {
    const request = vi.fn(async (path: string, _init?: unknown) => path.includes('by-idempotency-key') ? operation : { operation: { ...operation, kind: 'cancelRecordStatuses', idempotencyKey: 'cancel-key' } })
    const api = createStatusBatchApi({ request } as unknown as StreamingApiClient, 'p', 't')
    await api.lookup('start-key', () => true)
    await api.cancel('op', 2, 'cancel-key', () => true)
    expect(request.mock.calls[1][0]).toContain('/op/cancel')
    expect(request.mock.calls[1][1]).toMatchObject({ body: { expectedOperationRevision: 2 } })
  })
})
