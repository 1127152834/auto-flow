import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import type { SheetsApi } from '../sheets-api'
import { SheetsIdentityInitialization } from './SheetsIdentityInitialization'

afterEach(cleanup)
const request = { connectionId: 'c', spreadsheetId: 's', sheetId: 1000, expectedTableRevision: 3, identityStrategy: { kind: 'system' as const, columnId: 'C' }, mapping: [] }
const report = { impactRevision: 12, expectedRevisions: { tableRevision: 3 }, impacts: [], blockers: [] }
const setup = (items: object[] = []) => ({
  operations: vi.fn().mockResolvedValue({ items, pageSize: 100, total: items.length }),
  previewBinding: vi.fn().mockResolvedValue(report), previewIdentity: vi.fn().mockResolvedValue(report),
  initializeIdentity: vi.fn().mockResolvedValue({ status: 'reconciling' }),
  verifyIdentity: vi.fn().mockResolvedValue({ status: 'succeeded', result: { spreadsheetId: 's' } }), retryIdentity: vi.fn(),
})
const wrap = (api: object, onBound = vi.fn()) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <SheetsIdentityInitialization api={api as SheetsApi} scopeKey="ws:p" tableId="t" request={request} disabled={false} onBound={onBound} />
</QueryClientProvider>)

it('requires explicit source-write confirmation and never reports an unknown send as bound', async () => {
  const api = setup(), onBound = vi.fn()
  wrap(api, onBound)
  const button = screen.getByRole('button', { name: '初始化系统身份并绑定' })
  expect(button).toBeDisabled()
  await userEvent.click(screen.getByRole('checkbox'))
  await waitFor(() => expect(button).toBeEnabled())
  await userEvent.click(button)
  await waitFor(() => expect(api.initializeIdentity).toHaveBeenCalledWith('t', { ...request, impactRevision: 12 }, expect.any(String), expect.any(Function)))
  expect(await screen.findByText(/初始化结果尚未确认/)).toBeVisible()
  expect(onBound).not.toHaveBeenCalled()
})

it('loads the original unknown operation and verifies it without another initialization', async () => {
  const api = setup([{ syncOperationId: 'original', kind: 'systemIdentity', status: 'unknown' }]), onBound = vi.fn()
  wrap(api, onBound)
  await userEvent.click(await screen.findByRole('button', { name: '核验原初始化' }))
  await waitFor(() => expect(api.verifyIdentity).toHaveBeenCalledWith('t', 'original', { impactRevision: 12, expectedTableRevision: 3 }))
  expect(api.initializeIdentity).not.toHaveBeenCalled()
  expect(api.retryIdentity).not.toHaveBeenCalled()
  expect(onBound).toHaveBeenCalledWith({ spreadsheetId: 's' })
})

it('does not apply a late old-workspace result after the component is removed', async () => {
  let resolve!: (value: object) => void
  const api = setup(), onBound = vi.fn()
  api.initializeIdentity.mockImplementation(() => new Promise(done => { resolve = done }))
  const view = wrap(api, onBound)
  await userEvent.click(screen.getByRole('checkbox'))
  await userEvent.click(screen.getByRole('button', { name: '初始化系统身份并绑定' }))
  await waitFor(() => expect(api.initializeIdentity).toHaveBeenCalled())
  view.unmount()
  resolve({ status: 'succeeded', result: { spreadsheetId: 's' } })
  await Promise.resolve()
  expect(onBound).not.toHaveBeenCalled()
})
