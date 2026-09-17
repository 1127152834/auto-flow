import { expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../shared/api/client'
import type { InputTableOption } from './components/InputPlanEditor'
import { createAutomationResourcesApi } from './resources-api'

const internal = '11111111-2222-4333-8444-555555555555'
const field = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: 'business-id' }, key: 'business-id', name: '业务编号', type: 'string' as const, required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 }
const table = (identity: InputTableOption['identity']): InputTableOption => ({ id: 't', name: '资料表', datasetGeneration: 'g', identity, fields: [field], statuses: [], slotDefinitions: [] })
const record = (value: string) => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'uuid' as const, value: internal } }, values: [{ fieldId: 'business-id', value, source: 'local' as const, readable: true }], recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 1, statusRevision: 1, linkRevision: 1, deleted: false, createdAt: '2026-09-15T04:41:00Z', updatedAt: '2026-09-15T04:41:00Z' })

it('uses business text for system records and preserves a user UUID field identity', async () => {
  const request = vi.fn().mockResolvedValue({ items: [record('客户资料')], total: 1, page: 1, pageSize: 200 })
  const client = { request, stream: vi.fn(), health: vi.fn() } as StreamingApiClient
  const api = createAutomationResourcesApi(client, 'p')
  expect((await api.records(table({ mode: 'system' }), 1)).items[0].label).toBe('客户资料')
  request.mockResolvedValueOnce({ items: [record(internal)], total: 1, page: 1, pageSize: 200 })
  expect((await api.records(table({ mode: 'field', fieldId: 'business-id' }), 1)).items[0].label).toBe(internal)
})

it('never falls back to a system record key when business text is unavailable', async () => {
  const value = record('')
  value.values = []
  const request = vi.fn().mockResolvedValue({ items: [value], total: 1, page: 1, pageSize: 200 })
  const client = { request, stream: vi.fn(), health: vi.fn() } as StreamingApiClient
  const label = (await createAutomationResourcesApi(client, 'p').records(table({ mode: 'system' }), 1)).items[0].label
  expect(label).toMatch(/^未命名记录 · /)
  expect(label).not.toContain(internal)
})
