import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { BulkActions } from '../components/BulkActions'
import { DataMaintenance } from '../components/DataMaintenance'

const device = { deviceId: 'd1', revision: 2, name: '设备一', runtimeState: 'ready', owner: { kind: 'none', id: null }, observedAt: null, stale: false, specSnapshot: {}, latestOperation: null, allowedActions: ['start'], blockedReasons: {} } as never

it('freezes selected revisions when submitting a bulk action', async () => {
  const bulk = vi.fn(async (body: Record<string, unknown>) => ({ id: 'b', requestId: body.requestId as string, action: 'start', deleteData: false, state: 'queued', items: [], createdAt: '' }))
  render(<BulkActions api={{ bulk }} devices={[device]} />)
  await userEvent.click(screen.getByLabelText('设备一'))
  await userEvent.click(screen.getByRole('button', { name: '提交批量操作' }))
  expect(bulk).toHaveBeenCalledWith(expect.objectContaining({ items: [{ deviceId: 'd1', expectedRevision: 2 }] }))
})

it('requires a preview before cleanup execution', async () => {
  const cleanupPreview = vi.fn(async () => ({ items: [{ id: 'v1' }], confirmationDigest: 'digest' }))
  const cleanup = vi.fn(async () => ({ items: [], state: 'accepted' }))
  const diagnostics = vi.fn(async () => ({ id: 'd', requestId: 'r', state: 'ready', payload: {}, createdAt: '' }))
  render(<QueryClientProvider client={new QueryClient()}><DataMaintenance api={{ cleanupPreview, cleanup, diagnostics }} resourceIds={['v1']} /></QueryClientProvider>)
  expect(screen.queryByRole('button', { name: /确认清理/ })).not.toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '预览清理' }))
  expect(await screen.findByRole('button', { name: '确认清理 1 项' })).toBeVisible()
})
