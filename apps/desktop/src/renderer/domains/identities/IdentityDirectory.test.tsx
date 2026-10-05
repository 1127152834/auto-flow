import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../shared/api/client'
import { IdentityDirectory } from './IdentityDirectory'

const projectId = '00000000-0000-4000-8000-000000000001'
const identity = (overrides: Record<string, unknown>) => ({
  identityId: 'i1', projectId, name: '店铺账号 01', seedFingerprint: 'a1b2c3d4e5', legacySharedSeed: false,
  templateProfileId: null, environmentId: null, region: {},
  health: { lastLoginSuccessAt: null, consecutiveFailures: 0, banned: false },
  createdAt: '2026-10-04T00:00:00Z', updatedAt: '2026-10-04T00:00:00Z', ...overrides,
})

beforeEach(() => { vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' }) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function harness(items: unknown[]) {
  const calls: { path: string; method?: string; body?: unknown }[] = []
  const request = vi.fn(async (path: string, init?: { method?: string; body?: unknown }) => {
    calls.push({ path, method: init?.method, body: init?.body })
    if (!init?.method) return { items }
    return items[0]
  }) as unknown as StreamingApiClient['request']
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <IdentityDirectory client={{ request } as unknown as StreamingApiClient} projectId={projectId} scope={['w', 'i']} disabled={false} />
  </QueryClientProvider>)
  return calls
}

it('lists identities by fingerprint label and flags a kept older duplicate', async () => {
  harness([identity({}), identity({ identityId: 'i2', name: '旧账号', seedFingerprint: 'f9e8d7c6b5', legacySharedSeed: true, environmentId: 'e1', health: { lastLoginSuccessAt: null, consecutiveFailures: 3, banned: false } })])
  expect(await screen.findByText('店铺账号 01')).toBeVisible()
  expect(screen.getByText('a1b2c3d4e5', { selector: 'code' })).toBeVisible()
  expect(screen.getByText('与其他身份共用旧指纹')).toBeVisible()
  expect(screen.getByText('连续登录失败 3 次')).toBeVisible()
  // An identity holding a saved login cannot be deleted from here.
  expect(screen.getAllByRole('button', { name: '删除' })[1]).toBeDisabled()
})

it('creates with an idempotency key and asks before regenerating a fingerprint', async () => {
  const calls = harness([identity({})])
  await screen.findByText('店铺账号 01')
  await userEvent.type(screen.getByLabelText('新身份名称'), '店铺账号 02')
  await userEvent.click(screen.getByRole('button', { name: '新建身份' }))
  await waitFor(() => expect(calls.some(call => call.method === 'POST' && (call.body as { name?: string })?.name === '店铺账号 02')).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: '换新指纹' }))
  expect(screen.getByText(/可能需要重新验证/)).toBeVisible()
  expect(calls.some(call => call.path.endsWith('/regenerate-seed'))).toBe(false)
  await userEvent.click(screen.getAllByRole('button', { name: '换新指纹' }).at(-1)!)
  await waitFor(() => expect(calls.find(call => call.path.endsWith('/regenerate-seed'))?.body).toEqual({ confirmRegenerate: true }))
})
