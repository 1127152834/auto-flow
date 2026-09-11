// @vitest-environment node
import { mkdir, mkdtemp, realpath, symlink, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { createRevealKernelHandler, type KernelPathDependencies } from './kernel-paths'

async function setup(overrides: Partial<KernelPathDependencies> = {}) {
  const tmp = await mkdtemp(join(tmpdir(), 'autoflow-kernel-ipc-'))
  const executable = join(tmp, 'data', 'kernels', 'chromium-146.0.7680.80', 'chrome.exe')
  await mkdir(join(executable, '..'), { recursive: true })
  await writeFile(executable, 'kernel')
  const showItemInFolder = vi.fn()
  const dependencies: KernelPathDependencies = {
    allowedSenderId: 7,
    getSidecarStatus: () => ({
      state: 'ready', baseUrl: 'http://127.0.0.1:43127',
      hostToken: 'host-only-token', dataDir: tmp,
    }),
    request: vi.fn(async () => new Response(JSON.stringify({ executablePath: executable }))),
    showItemInFolder,
    ...overrides,
  }
  const mainFrame = {}
  return { dependencies, handler: createRevealKernelHandler(dependencies), mainFrame, executable, showItemInFolder, tmp }
}

describe('kernel reveal IPC', () => {
  it('resolves an installation ref through the host-only sidecar endpoint', async () => {
    const context = await setup()
    const event = { sender: { id: 7, mainFrame: context.mainFrame }, senderFrame: context.mainFrame }

    await expect(context.handler(event, { edition: 'public', version: '146.0.7680.80' })).resolves.toEqual({ revealed: true })

    expect(context.dependencies.request).toHaveBeenCalledWith(
      'http://127.0.0.1:43127/internal/kernels/resolve',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'x-autoflow-host-token': 'host-only-token' }),
        body: JSON.stringify({ edition: 'public', version: '146.0.7680.80' }),
      }),
    )
    expect(context.showItemInFolder).toHaveBeenCalledWith(await realpath(context.executable))
  })

  it.each([
    [8, true, { edition: 'public', version: '146.0.7680.80' }],
    [7, false, { edition: 'public', version: '146.0.7680.80' }],
    [7, true, { edition: 'public', version: '../../escape' }],
    [7, true, { edition: 'other', version: '146.0.7680.80' }],
    [7, true, { edition: 'public', version: '146.0.7680.80', executablePath: '/tmp/x' }],
  ])('rejects untrusted senders and renderer-controlled paths', async (senderId, main, value) => {
    const context = await setup()
    const senderFrame = main ? context.mainFrame : {}
    await expect(context.handler(
      { sender: { id: senderId as number, mainFrame: context.mainFrame }, senderFrame }, value,
    )).rejects.toThrow()
    expect(context.dependencies.request).not.toHaveBeenCalled()
  })

  it('rejects paths outside the configured sidecar data directory and symlink escapes', async () => {
    const outsideRoot = await mkdtemp(join(tmpdir(), 'autoflow-kernel-outside-'))
    const outside = join(outsideRoot, 'outside-kernel.exe')
    await writeFile(outside, 'outside')
    const outsideContext = await setup({
      request: vi.fn(async () => new Response(JSON.stringify({ executablePath: outside }))),
    })
    const event = { sender: { id: 7, mainFrame: outsideContext.mainFrame }, senderFrame: outsideContext.mainFrame }
    await expect(outsideContext.handler(event, { edition: 'public', version: '146.0.7680.80' })).rejects.toThrow('kernel reveal failed')

    const link = join(outsideContext.tmp, 'data', 'kernels', 'chromium-146.0.7680.80', 'linked.exe')
    await symlink(outside, link)
    const symlinkContext = await setup({
      request: vi.fn(async () => new Response(JSON.stringify({ executablePath: link }))),
      getSidecarStatus: outsideContext.dependencies.getSidecarStatus,
    })
    const linkedEvent = { sender: { id: 7, mainFrame: symlinkContext.mainFrame }, senderFrame: symlinkContext.mainFrame }
    await expect(symlinkContext.handler(linkedEvent, { edition: 'public', version: '146.0.7680.80' })).rejects.toThrow('kernel reveal failed')
  })

  it('rejects non-loopback sidecars without sending a request', async () => {
    const context = await setup({
      getSidecarStatus: () => ({ state: 'ready', baseUrl: 'https://example.test', hostToken: 'secret', dataDir: '/tmp' }),
    })
    const event = { sender: { id: 7, mainFrame: context.mainFrame }, senderFrame: context.mainFrame }
    await expect(context.handler(event, { edition: 'public', version: '146.0.7680.80' })).rejects.toThrow('kernel reveal failed')
    expect(context.dependencies.request).not.toHaveBeenCalled()
  })
})
