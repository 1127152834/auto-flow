import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockRequest, configureMock } from '../api/mock-server'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'])('image resource commands over %s', mode => {
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let request: (path: string, method?: string, body?: unknown) => Promise<Response>
  beforeEach(async () => {
    const storage = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
    localStorage.setItem('autoflow:studio:mock:image-assets', JSON.stringify({ folders: ['a', 'a/child', 'ab'], assets: [
      { id: 'one', name: 'one.png', originalName: 'one.png', folder: 'a/child', path: 'data:image/png;base64,eA==', dataUrl: 'data:image/png;base64,eA==' },
      { id: 'neighbor', name: 'other.png', originalName: 'other.png', folder: 'ab', path: 'data:image/png;base64,eA==', dataUrl: 'data:image/png;base64,eA==' },
    ] }))
    if (mode === 'http') fixture = await startHttpStudioFixture(mockRequest)
    request = (path, method = 'GET', body) => {
      const init = { method, ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) }
      return fixture ? fetch(`${fixture.origin}/api/image-assets${path}`, init) : mockRequest(`http://autoflow-studio.mock/api/image-assets${path}`, init)
    }
  })
  afterEach(async () => { configureMock({ disconnect: true }); await fixture?.close(); fixture = undefined; vi.unstubAllGlobals() })
  const stored = () => JSON.parse(localStorage.getItem('autoflow:studio:mock:image-assets')!)

  it('creates a folder and moves an image with the confirmed location fields', async () => {
    expect(await (await request('/folders', 'POST', { name: 'new', parentPath: 'a' })).json()).toEqual({ success: true, path: 'a/new' })
    expect(await (await request('/move', 'PUT', { assetId: 'one', targetFolder: 'a/new' })).json()).toEqual({ success: true, newFolder: 'a/new' })
    expect(stored().assets[0].folder).toBe('a/new')
    const before=stored()
    expect((await request('/folders', 'POST', { name: 'new', parentPath: 'a' })).status).toBe(400)
    expect(stored()).toEqual(before)
  })
  it.each(['', '../bad', 'bad\\name'])('rejects an invalid image name %j without changing metadata', async name => {
    const before=stored()
    expect((await request(`/one/rename?newName=${encodeURIComponent(name)}`, 'PUT')).status).toBe(400)
    expect(stored()).toEqual(before)
  })
  it('renames an image with the asset envelope required by the panel', async () => {
    const response = await request('/one/rename?newName=renamed.png', 'PUT')
    expect(response.status).toBe(200)
    expect(await response.json()).toMatchObject({ success: true, asset: { id: 'one', originalName: 'renamed.png' } })
    expect(stored().assets[0].originalName).toBe('renamed.png')
  })
  it.each(['', '.', '..', 'bad/name', 'bad\\name', '   '])('rejects invalid folder name %j without changing the library', async name => {
    const before = stored()
    expect((await request('/folders', 'POST', { name })).status).toBe(400)
    expect(stored()).toEqual(before)
  })
  it('rejects a missing resource move and preserves the library', async () => {
    const before = stored()
    expect((await request('/move', 'PUT', { assetId: 'missing', targetFolder: 'b' })).status).toBe(404)
    expect(stored()).toEqual(before)
  })
  it('protects the root folder from deletion', async () => {
    const before = stored()
    expect((await request('/folders', 'DELETE', { folderPath: '' })).status).toBe(400)
    expect(stored()).toEqual(before)
  })
  it('rejects missing and conflicting folder renames', async () => {
    const before = stored()
    expect((await request('/folders/rename', 'PUT', { oldPath: 'missing', newName: 'x' })).status).toBe(404)
    expect((await request('/folders/rename', 'PUT', { oldPath: 'a', newName: 'ab' })).status).toBe(400)
    expect(stored()).toEqual(before)
  })
  it('renames and deletes a subtree without modifying a neighboring prefix', async () => {
    expect(await (await request('/folders/rename', 'PUT', { oldPath: 'a', newName: 'renamed' })).json()).toMatchObject({ success: true, newPath: 'renamed' })
    expect(stored().assets.map((asset: { folder: string }) => asset.folder)).toEqual(['renamed/child', 'ab'])
    expect(await (await request('/folders', 'DELETE', { folderPath: 'renamed' })).json()).toMatchObject({ success: true, deletedCount: 1 })
    expect(stored().folders).toEqual(['ab']); expect(stored().assets.map((asset: { id: string }) => asset.id)).toEqual(['neighbor'])
  })
})
