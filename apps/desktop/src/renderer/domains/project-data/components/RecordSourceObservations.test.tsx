import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import type { SheetsApi } from '../sheets-api'
import { RecordSourceObservations } from './RecordSourceObservations'

type S = components['schemas']
afterEach(cleanup)
const ref: S['DataRecordRef'] = { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: '001' } }
const record: S['DataRecordView'] = { ref, values: [], recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 4, statusRevision: 1, linkRevision: 1, deleted: false, createdAt: '', updatedAt: '' }
const fields: S['DataFieldView'][] = [{ ref: { ...ref, fieldId: 'f' }, key: 'name', name: '名称', type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 }]
const observation: S['SourceRecordObservations'] = { record: ref, bindingEpoch: 1, items: [{ fieldId: 'f', remoteValue: '来源内容', localValue: '本地内容', localPresent: true, localContentRevision: 3, observedAt: '2026-09-21T12:00:00Z', differs: true }] }
it('shows source and observed local values separately using only a cancellable read', async () => {
  const observations = vi.fn().mockResolvedValue(observation)
  const api = { observations } as unknown as SheetsApi
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(<QueryClientProvider client={queryClient}><RecordSourceObservations api={api} scopeKey="workspace" record={record} fields={fields} /></QueryClientProvider>)
  expect(await screen.findByText('来源值：来源内容')).toBeVisible()
  expect(screen.getByText('观察时本地值：本地内容')).toBeVisible()
  expect(screen.getByText(/本地版本 3/)).toBeVisible()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  expect(observations).toHaveBeenCalledWith(ref, expect.any(AbortSignal))
  observations.mockResolvedValue({ record: { ...ref, datasetGeneration: 'new' }, bindingEpoch: 2, items: [] })
  view.rerender(<QueryClientProvider client={queryClient}><RecordSourceObservations api={api} scopeKey="workspace" record={{ ...record, ref: { ...ref, datasetGeneration: 'new' } }} fields={fields} /></QueryClientProvider>)
  expect(screen.queryByText('来源值：来源内容')).not.toBeInTheDocument()
  expect(await screen.findByText('当前绑定尚无普通字段观察。')).toBeVisible()
})
