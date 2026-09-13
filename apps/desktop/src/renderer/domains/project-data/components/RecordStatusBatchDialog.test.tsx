import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { RecordStatusBatchDialog } from './RecordStatusBatchDialog'
import { DataCommandNotAccepted, DataCommandUncertain } from '../data-command'

const ref = { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text' as const, value: 'one' } }
const record = { ref, statusRevision: 3, statusId: null } as never
const status = { statusId: 's', name: '完成', color: '#fff', order: 1, statusRevision: 1 }

beforeEach(() => { const values = new Map<string, string>(); vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('freezes selected records, previews blockers, then submits one durable command', async () => {
  const api = {
    preview: vi.fn(async () => ({ request: {}, checkedAt: '', blocks: [{ blockers: [{ message: '记录已变化' }] }] })),
    start: vi.fn(async () => ({ operationId: 'op', idempotencyKey: 'key', kind: 'setRecordStatuses', projectId: 'p', status: 'accepted', statusRevision: 1, result: null, error: null, resource: { type: 'table', projectId: 'p', tableId: 't' } })),
    lookup: vi.fn(async () => ({ operationId: 'op', idempotencyKey: 'key', kind: 'setRecordStatuses', projectId: 'p', status: 'accepted', statusRevision: 1, result: null, error: null, resource: { type: 'table', projectId: 'p', tableId: 't' } })), cancel: vi.fn(),
  }
  render(<RecordStatusBatchDialog open sessionKey="draft" contextKey="w:i:p:t" storageScopeKey="w:p:t" records={[record]} statuses={[status]} api={api as never} onClose={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '预检批量状态' }))
  expect(await screen.findByText('记录已变化')).not.toBeNull()
  await userEvent.click(screen.getByRole('button', { name: '确认开始' }))
  expect(api.start).toHaveBeenCalledWith(expect.objectContaining({ targets: [{ recordRef: ref, expectedStatusRevision: 3 }] }), expect.any(String), expect.any(Function))
  expect(await screen.findByText('已接受，等待处理')).not.toBeNull()
})

it('submits the selection hook targets without rebuilding their frozen revision', async () => {
  const target = { recordRef: ref, expectedStatusRevision: 2 }, api = { preview: vi.fn(async () => ({ request: {}, checkedAt: '', blocks: [] })), start: vi.fn(async () => ({ operationId: 'op', idempotencyKey: 'key', kind: 'setRecordStatuses', status: 'accepted', statusRevision: 1, resource: { type: 'table', projectId: 'p', tableId: 't' }, result: null, error: null })), lookup: vi.fn(), cancel: vi.fn() }
  render(<RecordStatusBatchDialog open sessionKey="draft" contextKey="w:i:p:t" storageScopeKey="w:p:t" targets={[target]} statuses={[status]} api={api as never} onClose={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '预检批量状态' })); await userEvent.click(screen.getByRole('button', { name: '确认开始' }))
  expect(api.start).toHaveBeenCalledWith(expect.objectContaining({ targets: [target] }), expect.any(String), expect.any(Function))
})

it('ignores a late preview after context changes and recovers an accepted key', async () => {
  let finish!: (value: unknown) => void
  const preview = vi.fn(() => new Promise(resolve => { finish = resolve }))
  const api = { preview, start: vi.fn(), lookup: vi.fn(async () => ({ operationId: 'op', idempotencyKey: 'saved', kind: 'setRecordStatuses', projectId: 'p', status: 'failed', statusRevision: 3, resource: { type: 'table', projectId: 'p', tableId: 't' }, result: { blocks: [], changedCount: 2, conflictCount: 1, notStartedCount: 4, cancelled: false }, error: { message: '部分冲突' } })), cancel: vi.fn() }
  const props = { open: true, sessionKey: 'draft', storageScopeKey: 'w:p:t', records: [record], statuses: [status], api: api as never, onClose: vi.fn() }
  const view = render(<RecordStatusBatchDialog {...props} contextKey="w:i1:p:t" />)
  await userEvent.click(screen.getByRole('button', { name: '预检批量状态' }))
  view.rerender(<RecordStatusBatchDialog {...props} contextKey="w:i2:p:t" />)
  finish({ request: {}, checkedAt: '', blocks: [{ blockers: [{ message: '迟到结果' }] }] })
  await waitFor(() => expect(screen.queryByText('迟到结果')).toBeNull())

  localStorage.setItem('autoflow:status-batch:w:p:t', 'saved')
  view.rerender(<RecordStatusBatchDialog {...props} contextKey="w:i2:p:t" sessionKey="reopen" />)
  expect(await screen.findByText('操作未全部完成')).not.toBeNull()
  expect(screen.getByText('已修改 2 条')).not.toBeNull()
})

it('keeps the original start key and body until lookup proves it was not accepted', async () => {
  const accepted = { operationId: 'op', idempotencyKey: 'same', kind: 'setRecordStatuses', projectId: 'p', status: 'accepted', statusRevision: 1, result: null, error: null, resource: { type: 'table', projectId: 'p', tableId: 't' } }
  const start = vi.fn().mockRejectedValueOnce(new DataCommandUncertain(new Error('network'))).mockResolvedValue(accepted)
  const api = { preview: vi.fn(async () => ({ request: {}, checkedAt: '', blocks: [] })), start, lookup: vi.fn().mockRejectedValue(new DataCommandNotAccepted()), lookupCancel: vi.fn(), cancel: vi.fn() }
  const view = render(<RecordStatusBatchDialog open sessionKey="draft" contextKey="w:i1:p:t" storageScopeKey="w:p:t" records={[record]} statuses={[status]} api={api as never} onClose={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '预检批量状态' })); await userEvent.click(screen.getByRole('button', { name: '确认开始' }))
  const [body, key] = start.mock.calls[0]
  expect(JSON.parse(localStorage.getItem('autoflow:status-batch:w:p:t')!)).toEqual({ key, request: body })
  view.rerender(<RecordStatusBatchDialog open sessionKey="reopen" contextKey="w:i2:p:t" storageScopeKey="w:p:t" records={[record]} statuses={[status]} api={api as never} onClose={vi.fn()} />)
  await userEvent.click(await screen.findByRole('button', { name: '按原键重试' }))
  expect(start.mock.calls[1].slice(0, 2)).toEqual([body, key])
})

it('hydrates unknown identity and never offers a fresh preview or key', async () => {
  const pending = { key: 'original', request: { statusId: null, targets: [{ recordRef: ref, expectedStatusRevision: 3 }], blockSize: 100 } }
  localStorage.setItem('autoflow:status-batch:w:p:t', JSON.stringify(pending))
  const api = { preview: vi.fn(), start: vi.fn(), lookup: vi.fn().mockRejectedValue(new DataCommandUncertain(new Error('offline'))), lookupCancel: vi.fn(), cancel: vi.fn() }
  render(<RecordStatusBatchDialog open sessionKey="draft" contextKey="w:i:p:t" storageScopeKey="w:p:t" records={[record]} statuses={[status]} api={api as never} onClose={vi.fn()} />)
  expect(await screen.findByRole('button', { name: '核对原操作' })).not.toBeNull(); expect(screen.getByRole('button', { name: '预检批量状态' })).toBeDisabled()
  expect(api.start).not.toHaveBeenCalled()
})

it('rejects more than 1000 targets instead of truncating them', () => {
  render(<RecordStatusBatchDialog open sessionKey="draft" contextKey="w:i:p:t" storageScopeKey="w:p:t" records={Array.from({ length: 1001 }, () => record)} statuses={[status]} api={{} as never} onClose={vi.fn()} />)
  expect(screen.getByRole('alert')).toHaveTextContent('一次最多处理 1000 条'); expect(screen.getByRole('button', { name: '预检批量状态' })).toBeDisabled()
})

it('does not send when durable storage fails and releases busy state', async () => {
  const start = vi.fn(), api = { preview: vi.fn(async () => ({ request: {}, checkedAt: '', blocks: [] })), start, lookup: vi.fn(), lookupCancel: vi.fn(), cancel: vi.fn() }
  const view = render(<RecordStatusBatchDialog open sessionKey="draft" contextKey="w:i:p:t" storageScopeKey="w:p:t" records={[record]} statuses={[status]} api={api as never} onClose={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '预检批量状态' }))
  vi.spyOn(localStorage, 'setItem').mockImplementation(() => { throw new Error('storage unavailable') })
  await userEvent.click(screen.getByRole('button', { name: '确认开始' }))
  expect(start).not.toHaveBeenCalled(); expect(screen.getByRole('alert')).toHaveTextContent('storage unavailable'); expect(screen.getByRole('button', { name: '确认开始' })).not.toBeDisabled()
  view.unmount()
})

it('blocks every write after readonly changes and hides stop for terminal operations', async () => {
  const api = { preview: vi.fn(async () => ({ request: {}, checkedAt: '', blocks: [] })), start: vi.fn(), lookup: vi.fn(), lookupCancel: vi.fn(), cancel: vi.fn() }
  const props = { open: true, sessionKey: 'draft', contextKey: 'w:i:p:t', storageScopeKey: 'w:p:t', records: [record], statuses: [status], api: api as never, onClose: vi.fn() }
  const view = render(<RecordStatusBatchDialog {...props} />); await userEvent.click(screen.getByRole('button', { name: '预检批量状态' })); view.rerender(<RecordStatusBatchDialog {...props} readonly />)
  expect(screen.getByRole('button', { name: '确认开始' })).toBeDisabled()
  localStorage.setItem('autoflow:status-batch:w:p:t', 'saved'); api.lookup.mockResolvedValue({ operationId: 'op', idempotencyKey: 'saved', kind: 'setRecordStatuses', status: 'failed', statusRevision: 2, resource: { type: 'table', projectId: 'p', tableId: 't' }, result: { blocks: [], changedCount: 0, conflictCount: 0, notStartedCount: 1, cancelled: false }, error: null })
  view.rerender(<RecordStatusBatchDialog {...props} readonly sessionKey="reopen" />); await screen.findByText('操作未全部完成'); expect(screen.queryByRole('button', { name: '停止后续处理' })).toBeNull()
})

it('acknowledges success and lets the next session start a new batch', async () => {
  const succeeded = { operationId: 'op', idempotencyKey: 'key', kind: 'setRecordStatuses', status: 'succeeded', statusRevision: 2, resource: { type: 'table', projectId: 'p', tableId: 't' }, result: { blocks: [], changedCount: 1, conflictCount: 0, notStartedCount: 0, cancelled: false }, error: null }, completed = vi.fn()
  localStorage.setItem('autoflow:status-batch:w:p:t', 'key')
  render(<RecordStatusBatchDialog open sessionKey="reopen" contextKey="w:i:p:t" storageScopeKey="w:p:t" records={[record]} statuses={[status]} api={{ lookup: vi.fn().mockResolvedValue(succeeded) } as never} onClose={vi.fn()} onCompleted={completed} />)
  await waitFor(() => expect(completed).toHaveBeenCalledOnce()); expect(localStorage.getItem('autoflow:status-batch:w:p:t')).toBeNull()
})

it('keeps the cancel identity when restoring the original key cannot be persisted', async () => {
  const accepted = { operationId: 'op', idempotencyKey: 'original', kind: 'setRecordStatuses', status: 'accepted', statusRevision: 2, resource: { type: 'table', projectId: 'p', tableId: 't' }, result: null, error: null }
  localStorage.setItem('autoflow:status-batch:w:p:t', 'original')
  const api = { lookup: vi.fn().mockResolvedValue(accepted), lookupCancel: vi.fn(), cancel: vi.fn().mockRejectedValue(new Error('cancel rejected')) }
  render(<RecordStatusBatchDialog open sessionKey="reopen" contextKey="w:i:p:t" storageScopeKey="w:p:t" records={[record]} statuses={[status]} api={api as never} onClose={vi.fn()} />)
  await screen.findByText('已接受，等待处理')
  const realSet = localStorage.setItem.bind(localStorage); let writes = 0
  vi.spyOn(localStorage, 'setItem').mockImplementation((key, value) => { if (++writes === 2) throw new Error('restore failed'); realSet(key, value) })
  await userEvent.click(screen.getByRole('button', { name: '停止后续处理' })); await userEvent.click(screen.getByRole('button', { name: '确认停止' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('restore failed')
  expect(screen.getByRole('button', { name: '核对停止结果' })).toBeInTheDocument()
  expect(JSON.parse(localStorage.getItem('autoflow:status-batch:w:p:t')!)).toHaveProperty('cancel.operationId', 'op')
})
import '@testing-library/jest-dom/vitest'
