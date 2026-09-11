import { realpath } from 'node:fs/promises'
import { isAbsolute, join, relative, sep } from 'node:path'

export type KernelRef = {
  edition: 'public' | 'licensed'
  version: string
}

type SenderFrame = object
type InvokeEvent = { sender: { id: number; mainFrame: SenderFrame }; senderFrame: SenderFrame | null }
type SidecarStatus =
  | { state: 'ready'; baseUrl: string; hostToken: string; dataDir: string }
  | { state: 'stopped' }

export type KernelPathDependencies = {
  allowedSenderId: number
  getSidecarStatus: () => SidecarStatus
  request: typeof fetch
  showItemInFolder: (path: string) => void
}

const VERSION = /^[0-9]+(?:\.[0-9]+){3,4}$/

function validateRef(value: unknown): asserts value is KernelRef {
  if (!value || typeof value !== 'object') throw new Error('invalid kernel reference')
  const ref = value as Record<string, unknown>
  if (
    Object.keys(ref).sort().join(',') !== 'edition,version'
    || (ref.edition !== 'public' && ref.edition !== 'licensed')
    || typeof ref.version !== 'string'
    || !VERSION.test(ref.version)
  ) throw new Error('invalid kernel reference')
}

function endpoint(status: Extract<SidecarStatus, { state: 'ready' }>): string {
  let url: URL
  try {
    url = new URL(status.baseUrl)
  } catch {
    throw new Error('kernel path service is unavailable')
  }
  if (
    url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port
    || url.pathname !== '/' || url.username || url.password || url.search || url.hash
    || !status.hostToken || !isAbsolute(status.dataDir)
  ) throw new Error('kernel path service is unavailable')
  return `${url.origin}/internal/kernels/resolve`
}

export function createRevealKernelHandler(dependencies: KernelPathDependencies) {
  return async (event: InvokeEvent, value: unknown): Promise<{ revealed: true }> => {
    if (
      event.sender.id !== dependencies.allowedSenderId
      || event.senderFrame === null
      || event.senderFrame !== event.sender.mainFrame
    ) throw new Error('kernel reveal is not allowed')
    validateRef(value)
    const status = dependencies.getSidecarStatus()
    if (status.state !== 'ready') throw new Error('kernel path service is unavailable')

    let response: Response
    try {
      response = await dependencies.request(endpoint(status), {
        method: 'POST',
        cache: 'no-store',
        redirect: 'error',
        signal: AbortSignal.timeout(10_000),
        headers: {
          accept: 'application/json',
          'content-type': 'application/json',
          'x-autoflow-host-token': status.hostToken,
        },
        body: JSON.stringify(value),
      })
    } catch {
      throw new Error('kernel reveal failed')
    }
    if (!response.ok) throw new Error('kernel reveal failed')
    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new Error('kernel reveal failed')
    }
    const path = body && typeof body === 'object'
      ? (body as Record<string, unknown>).executablePath
      : undefined
    if (typeof path !== 'string' || !isAbsolute(path)) throw new Error('kernel reveal failed')

    try {
      const root = await realpath(join(status.dataDir, 'data', 'kernels'))
      const executable = await realpath(path)
      const inside = relative(root, executable)
      const expectedDirectory = `chromium-${value.version}${value.edition === 'licensed' ? '-pro' : ''}`
      if (
        !inside || inside === '..' || inside.startsWith(`..${sep}`) || isAbsolute(inside)
        || inside.split(sep)[0] !== expectedDirectory
      ) throw new Error('invalid managed path')
      dependencies.showItemInFolder(executable)
    } catch {
      throw new Error('kernel reveal failed')
    }
    return { revealed: true }
  }
}
