// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'
import { createCopyProxyCredentialsHandler, type ProxyCredentialDependencies } from './proxy-credentials'

function setup(overrides: Partial<ProxyCredentialDependencies> = {}) {
  let clipboardValue = ''
  let scheduled: (() => void) | undefined
  const dependencies: ProxyCredentialDependencies = {
    allowedSenderId: 7,
    getSidecarStatus: () => ({
      state: 'ready',
      baseUrl: 'http://127.0.0.1:43127',
      hostToken: 'host-only-token',
    }),
    request: vi.fn(async () => new Response(JSON.stringify({ value: 'proxy-password' }))),
    clipboard: {
      readText: () => clipboardValue,
      writeText: value => { clipboardValue = value },
    },
    schedule: (callback, delayMs) => {
      expect(delayMs).toBe(30_000)
      scheduled = callback
    },
    ...overrides,
  }
  return {
    dependencies,
    handler: createCopyProxyCredentialsHandler(dependencies),
    clipboard: () => clipboardValue,
    changeClipboard: (value: string) => { clipboardValue = value },
    runCleanup: () => scheduled?.(),
  }
}

describe('proxy credential copy IPC', () => {
  it('uses the host-only endpoint and clears unchanged clipboard content', async () => {
    const context = setup()
    const mainFrame = {}

    await expect(context.handler(
      { sender: { id: 7, mainFrame }, senderFrame: mainFrame },
      { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'socks5', format: 'password' },
    )).resolves.toEqual({ copied: true })

    expect(context.dependencies.request).toHaveBeenCalledWith(
      'http://127.0.0.1:43127/internal/proxy-credentials/resolve',
      expect.objectContaining({
        method: 'POST',
        cache: 'no-store',
        headers: expect.objectContaining({ 'x-autoflow-host-token': 'host-only-token' }),
        body: JSON.stringify({ proxy_id: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'socks5', format: 'password' }),
      }),
    )
    expect(context.clipboard()).toBe('proxy-password')
    context.runCleanup()
    expect(context.clipboard()).toBe('')
  })

  it('does not overwrite newer clipboard content during cleanup', async () => {
    const context = setup()
    const mainFrame = {}
    await context.handler(
      { sender: { id: 7, mainFrame }, senderFrame: mainFrame },
      { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'http', format: 'url' },
    )

    context.changeClipboard('newer-user-copy')
    context.runCleanup()

    expect(context.clipboard()).toBe('newer-user-copy')
  })

  it.each([
    [8, true, { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'http', format: 'url' }],
    [7, false, { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'http', format: 'url' }],
    [7, true, { proxyId: '../secret', protocol: 'http', format: 'url' }],
    [7, true, { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'ftp', format: 'url' }],
    [7, true, { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'http', format: 'raw' }],
  ])('rejects untrusted senders and uncontrolled parameters', async (senderId, isMainFrame, request) => {
    const context = setup()
    const mainFrame = {}
    const senderFrame = isMainFrame ? mainFrame : {}
    await expect(context.handler(
      { sender: { id: senderId, mainFrame }, senderFrame },
      request,
    )).rejects.toThrow()
    expect(context.dependencies.request).not.toHaveBeenCalled()
    expect(context.clipboard()).toBe('')
  })

  it('rejects non-loopback sidecar targets', async () => {
    const context = setup({
      getSidecarStatus: () => ({ state: 'ready', baseUrl: 'https://example.test', hostToken: 'host-only-token' }),
    })
    const mainFrame = {}

    await expect(context.handler(
      { sender: { id: 7, mainFrame }, senderFrame: mainFrame },
      { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'http', format: 'username' },
    )).rejects.toThrow('credential copy failed')
    expect(context.dependencies.request).not.toHaveBeenCalled()
  })

  it('does not copy when the sidecar is unavailable or exposes request errors', async () => {
    const mainFrame = {}
    const unavailable = setup({ getSidecarStatus: () => ({ state: 'starting' }) })
    await expect(unavailable.handler(
      { sender: { id: 7, mainFrame }, senderFrame: mainFrame },
      { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'http', format: 'password' },
    )).rejects.toThrow('credential service is unavailable')

    const failed = setup({
      request: vi.fn(async () => { throw new Error('host-only-token proxy-password') }),
    })
    await expect(failed.handler(
      { sender: { id: 7, mainFrame }, senderFrame: mainFrame },
      { proxyId: '4cc4bd80-8f6a-48a7-a989-748e43a45389', protocol: 'http', format: 'password' },
    )).rejects.toThrow(/^credential copy failed$/)
    expect(unavailable.clipboard()).toBe('')
    expect(failed.clipboard()).toBe('')
  })
})
