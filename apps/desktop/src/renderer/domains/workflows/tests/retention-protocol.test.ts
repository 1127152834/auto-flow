import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'] as const)('retention protocol: %s', mode => {
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let request: (path: string, init?: RequestInit) => Promise<Response>
  beforeEach(async () => {
    const storage = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) })
    const server = await import('../api/mock-server')
    if (mode === 'http') { fixture = await startHttpStudioFixture(server.mockRequest); request = (path, init) => fetch(`${fixture!.origin}/api${path}`, init) }
    else request = (path, init) => server.mockRequest(`http://autoflow-studio.mock/api${path}`, init)
  })
  afterEach(async () => { await fixture?.close(); fixture = undefined; vi.unstubAllGlobals() })
  const post = (body: unknown) => ({ method: 'POST', body: JSON.stringify(body) })
  it('preserves AutoFlow defaults and confirms partial save on reopening', async () => {
    const before = await (await request('/retention/config')).json()
    expect(before.config).toMatchObject({ enabled: false, recordings_max_days: 30, cleanup_interval_hours: 24 })
    expect((await request('/retention/config', post({ data_max_days: 9 }))).status).toBe(200)
    expect((await (await request('/retention/config')).json()).config).toEqual({ ...before.config, data_max_days: 9 })
  })
  it.each([{ enabled: 'true' }, { data_max_days: -1 }, { data_max_days: 1.5 }, { data_max_days: '' }, { cleanup_interval_hours: 0 }, { data_max_days: 9007199254740992 }, { unexpected: 1 }])('rejects invalid update %j without changing persisted config', async body => {
    const before = await (await request('/retention/config')).json()
    expect((await request('/retention/config', post(body))).status).toBe(422)
    expect((await (await request('/retention/config')).json()).config).toEqual(before.config)
  })
  it('returns explicit zero Mock cleanup totals', async () => {
    expect(await (await request('/retention/cleanup', post({}))).json()).toEqual({ success: true, mock: true, recordings: { removed: 0, freedMB: 0 }, data: { removed: 0, freedMB: 0 } })
  })
  it.each([['/retention/cleanup', 'GET'], ['/retention/usage', 'POST'], ['/retention/config', 'DELETE']])('rejects %s %s', async (path, method) => {
    expect((await request(path, { method })).status).toBe(405)
  })
})
it('does not acknowledge a failed policy write', async () => {
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => { throw new Error('quota') } })
  try {
    const { mockSettingsRequest } = await import('../api/mock-settings')
    const response = mockSettingsRequest('/retention/config', 'POST', { data_max_days: 7 })!
    expect(response.status).toBe(507); expect(await response.json()).toMatchObject({ success: false })
  } finally { vi.unstubAllGlobals() }
})
