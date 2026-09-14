import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'] as const)('credential metadata protocol: %s', mode => {
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let request: (path: string, init?: RequestInit) => Promise<Response>
  let storage: Map<string, string>
  beforeEach(async () => {
    storage = new Map()
    vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
    vi.resetModules()
    const server = await import('../api/mock-server')
    if (mode === 'http') {
      fixture = await startHttpStudioFixture(server.mockRequest)
      request = (path, init) => fetch(`${fixture!.origin}/api${path}`, init)
    } else request = (path, init) => server.mockRequest(`http://autoflow-studio.mock/api${path}`, init)
  })
  afterEach(async () => { await fixture?.close(); fixture = undefined; vi.unstubAllGlobals() })
  const post = (body: unknown) => ({ method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
  it.each([['/credentials', 'PUT'], ['/credentials/names', 'POST'], ['/credentials/rename', 'GET']])('rejects unsupported %s %s', async (path, method) => {
    expect((await request(path, { method })).status).toBe(405)
  })
  it.each(['names', 'rename', '__proto__', 'constructor', '中文 凭据'])('stores and deletes the literal name %s', async name => {
    expect((await request('/credentials', post({ name, fields: { value: 'dummy-only' } }))).status).toBe(200)
    expect((await (await request('/credentials/names')).json()).names).toContain(name)
    expect((await request(`/credentials/${encodeURIComponent(name)}`, { method: 'DELETE' })).status).toBe(200)
    expect((await (await request('/credentials/names')).json()).names).not.toContain(name)
    expect((await request(`/credentials/${encodeURIComponent(name)}`, { method: 'DELETE' })).status).toBe(404)
  })
  it('preserves existing metadata fields on partial upsert without storing secret values', async () => {
    await request('/credentials', post({ name: 'fixture', description: '保留说明', fields: { value: 'dummy-first', password: 'dummy-second' } }))
    await request('/credentials', post({ name: 'fixture', description: '', fields: { value: '' } }))
    const result = await (await request('/credentials')).json()
    expect(result.credentials[0]).toMatchObject({ description: '保留说明', fields: [{ key: 'value' }, { key: 'password' }] })
    expect([...storage.values()].join('')).not.toMatch(/dummy-first|dummy-second/)
  })
  it.each([
    [{ name: 1, fields: { value: 'x' } }, 422],
    [{ name: 'x', fields: [] }, 422],
    [{ name: 'x', fields: { value: 1 } }, 422],
    [{ name: '', fields: { value: 'x' } }, 400],
    [{ name: 'x', fields: {} }, 400],
  ])('rejects invalid upsert %j without adding metadata', async (body, status) => {
    expect((await request('/credentials', post(body))).status).toBe(status)
    expect((await (await request('/credentials/names')).json()).names).toEqual([])
  })
  it.each([
    [{ old_name: 1, new_name: 'new' }, 422],
    [{ old_name: 'fixture', new_name: ' ' }, 400],
    [{ old_name: 'missing', new_name: 'new' }, 404],
  ])('rejects invalid rename %j without changing metadata', async (body, status) => {
    await request('/credentials', post({ name: 'fixture', fields: { value: '' } }))
    expect((await request('/credentials/rename', post(body))).status).toBe(status)
    expect((await (await request('/credentials/names')).json()).names).toEqual(['fixture'])
  })
  it.each(['fixture', '__proto__'])('renames safely to %s and preserves metadata', async name => {
    await request('/credentials', post({ name: 'fixture', description: '说明', fields: { value: '' } }))
    expect((await request('/credentials/rename', post({ old_name: 'fixture', new_name: name }))).status).toBe(200)
    const result = await (await request('/credentials')).json()
    expect(result.credentials).toHaveLength(1)
    expect(result.credentials[0]).toMatchObject({ name, description: '说明', fields: [{ key: 'value' }] })
  })
  it('keeps both entries when a rename target already exists', async () => {
    for (const name of ['one', 'two']) await request('/credentials', post({ name, fields: { value: '' } }))
    expect((await request('/credentials/rename', post({ old_name: 'one', new_name: 'two' }))).status).toBe(409)
    expect((await (await request('/credentials/names')).json()).names).toEqual(['one', 'two'])
  })
})
