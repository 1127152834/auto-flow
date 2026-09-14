// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'
import { registerProjectFileSelection } from './registry'

const host = {
  state: 'ready' as const,
  baseUrl: 'http://127.0.0.1:43127',
  hostToken: 'host-only-token',
  dataDir: '/workspace/data',
}

describe('project file selection registration', () => {
  it('registers the trusted native path through the host-only endpoint', async () => {
    const request = vi.fn(async () => new Response(null, { status: 204 }))
    const selection = {
      selectionToken: '4cc4bd80-8f6a-48a7-a989-748e43a45389',
      path: '/tmp/source.xlsx',
      projectId: '726a0f9e-a0e7-4b83-9794-b8d5946825e0',
      windowId: 7,
      purpose: 'inspectExcel' as const,
      expiresAt: '2026-09-13T12:05:00.000Z',
    }

    await registerProjectFileSelection(host, selection, 'window-proof-token', request)

    expect(request).toHaveBeenCalledWith(
      'http://127.0.0.1:43127/internal/project-files/selections',
      expect.objectContaining({
        method: 'POST', cache: 'no-store', redirect: 'error',
        headers: expect.objectContaining({
          'x-autoflow-host-token': 'host-only-token',
          'x-autoflow-file-window-token': 'window-proof-token',
        }),
        body: JSON.stringify(selection),
      }),
    )
  })

  it.each([
    [{ ...host, baseUrl: 'https://example.test' }],
    [{ ...host, baseUrl: 'http://localhost:43127' }],
    [{ ...host, baseUrl: 'http://127.0.0.1:43127/path' }],
    [{ ...host, hostToken: '' }],
  ])('rejects an untrusted host target', async invalidHost => {
    const request = vi.fn()
    await expect(registerProjectFileSelection(invalidHost, {
      selectionToken: crypto.randomUUID(), path: '/tmp/source.xlsx', projectId: crypto.randomUUID(),
      windowId: 7, purpose: 'inspectExcel', expiresAt: new Date().toISOString(),
    }, 'window-proof-token', request as typeof fetch)).rejects.toThrow('project file service is unavailable')
    expect(request).not.toHaveBeenCalled()
  })

  it('rejects an empty main-process window proof before sending', async () => {
    const request = vi.fn()
    await expect(registerProjectFileSelection(host, {
      selectionToken: crypto.randomUUID(), path: '/tmp/source.xlsx', projectId: crypto.randomUUID(),
      windowId: 7, purpose: 'inspectExcel', expiresAt: new Date().toISOString(),
    }, '', request as typeof fetch)).rejects.toThrow('project file service is unavailable')
    expect(request).not.toHaveBeenCalled()
  })
})
