import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'])('debug request validation over %s', mode => {
  let server: typeof import('../api/mock-server')
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let request: (action: string, body?: unknown, method?: string) => Promise<Response>
  beforeEach(async () => {
    const storage = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) })
    vi.resetModules(); server = await import('../api/mock-server')
    if (mode === 'http') fixture = await startHttpStudioFixture(server.mockRequest)
    request = (action, body = {}, method = 'POST') => {
      const init = { method, ...(method === 'GET' ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) }
      return fixture ? fetch(`${fixture.origin}/api${action}`, init) : server.mockRequest(`http://autoflow-studio.mock/api${action}`, init)
    }
    await request('/workflows', { id: 'debug-guard', name: '调试命令保护', nodes: [{ id: 'first', type: 'open_page' }, { id: 'next', type: 'click_element' }], variables: [] })
    await request('/workflows/debug-guard/execute', { breakpoints: ['first'] })
    await vi.waitFor(() => expect(server.mockSnapshot().sequence).toBe(2))
  })
  afterEach(async () => {
    if (server.mockSnapshot().run) await request('/workflows/debug-guard/stop')
    server.configureMock({ disconnect: true }); await fixture?.close(); fixture = undefined; vi.unstubAllGlobals()
  })
  it.each(['unknown', 'resume/extra', 'step/extra'])('rejects unknown action %s without resuming', async action => {
    const sequence = server.mockSnapshot().sequence
    expect((await request(`/workflows/debug-guard/debug/${action}`)).status).toBe(404)
    expect(server.mockSnapshot()).toMatchObject({ run: 'debug-guard', sequence })
  })
  it.each(['resume', 'step', 'breakpoints'])('rejects GET for %s without a side effect', async action => {
    const sequence = server.mockSnapshot().sequence
    expect((await request(`/workflows/debug-guard/debug/${action}`, undefined, 'GET')).status).toBe(405)
    expect(server.mockSnapshot()).toMatchObject({ run: 'debug-guard', sequence })
  })
  it.each([{}, { breakpoints: null }, { breakpoints: 'first' }, { breakpoints: [12] }, { breakpoints: ['missing'] }])('rejects invalid breakpoint update %j and retains the pause', async payload => {
    const sequence = server.mockSnapshot().sequence
    expect((await request('/workflows/debug-guard/debug/breakpoints', payload)).status).toBe(422)
    expect(server.mockSnapshot()).toMatchObject({ run: 'debug-guard', sequence })
    expect((await request('/workflows/debug-guard/debug/step')).status).toBe(200)
    await vi.waitFor(() => expect(server.mockSnapshot().sequence).toBeGreaterThan(sequence + 1))
    expect(server.mockSnapshot().run).toBe('debug-guard')
  })
  it('accepts an empty breakpoint set and rejects a second step while the node is running', async () => {
    expect((await request('/workflows/debug-guard/debug/breakpoints', { breakpoints: [] })).status).toBe(200)
    expect((await request('/workflows/debug-guard/debug/step')).status).toBe(200)
    const sequence = server.mockSnapshot().sequence
    expect((await request('/workflows/debug-guard/debug/step')).status).toBe(409)
    expect(server.mockSnapshot().sequence).toBe(sequence)
  })
  it.each([null, 'first', [12], ['missing']])('rejects invalid startup breakpoints %j before creating events', async breakpoints => {
    await request('/workflows/debug-guard/stop')
    const sequence = server.mockSnapshot().sequence
    expect((await request('/workflows/debug-guard/execute', { breakpoints })).status).toBe(422)
    expect(server.mockSnapshot()).toMatchObject({ run: null, sequence })
  })
  it('allows breakpoints in the snapshot even when the fixture trajectory skips that branch', async () => {
    await request('/workflows/debug-guard/stop')
    server.configureMock({ executionOrder: ['first'] })
    expect((await request('/workflows/debug-guard/execute', { breakpoints: ['first', 'next'] })).status).toBe(200)
    expect((await request('/workflows/debug-guard/debug/breakpoints', { breakpoints: ['next'] })).status).toBe(200)
  })

})
