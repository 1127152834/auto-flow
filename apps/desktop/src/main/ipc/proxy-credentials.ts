export type ProxyCredentialProtocol = 'http' | 'socks5'
export type ProxyCredentialFormat = 'username' | 'password' | 'url'

export type CopyProxyCredentialsRequest = {
  proxyId: string
  protocol: ProxyCredentialProtocol
  format: ProxyCredentialFormat
}

type Sender = { id: number }
type SenderFrame = object
type InvokeEvent = { sender: Sender & { mainFrame: SenderFrame }; senderFrame: SenderFrame | null }
type SidecarStatus =
  | { state: 'ready'; baseUrl: string; hostToken: string }
  | { state: 'starting' | 'stopped' | 'failed' }
type Clipboard = { readText: () => string; writeText: (value: string) => void }
type Schedule = (callback: () => void, delayMs: number) => unknown

export type ProxyCredentialDependencies = {
  allowedSenderId: number
  getSidecarStatus: () => SidecarStatus
  request: typeof fetch
  clipboard: Clipboard
  schedule?: Schedule
}

const PROXY_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const PROTOCOLS = new Set<ProxyCredentialProtocol>(['http', 'socks5'])
const FORMATS = new Set<ProxyCredentialFormat>(['username', 'password', 'url'])

function validateRequest(value: unknown): asserts value is CopyProxyCredentialsRequest {
  if (!value || typeof value !== 'object') throw new Error('invalid credential copy request')
  const request = value as Record<string, unknown>
  if (
    typeof request.proxyId !== 'string'
    || !PROXY_ID.test(request.proxyId)
    || !PROTOCOLS.has(request.protocol as ProxyCredentialProtocol)
    || !FORMATS.has(request.format as ProxyCredentialFormat)
  ) {
    throw new Error('invalid credential copy request')
  }
}

function internalEndpoint(status: Extract<SidecarStatus, { state: 'ready' }>): string {
  let url: URL
  try {
    url = new URL(status.baseUrl)
  } catch {
    throw new Error('credential service is unavailable')
  }
  if (
    url.protocol !== 'http:'
    || url.hostname !== '127.0.0.1'
    || !url.port
    || url.pathname !== '/'
    || url.username
    || url.password
    || url.search
    || url.hash
  ) {
    throw new Error('credential service is unavailable')
  }
  if (!status.hostToken) throw new Error('credential service is unavailable')
  return `${url.origin}/internal/proxy-credentials/resolve`
}

async function clearIfUnchanged(clipboard: Clipboard, copiedValue: string): Promise<void> {
  try {
    if (clipboard.readText() === copiedValue) clipboard.writeText('')
  } catch {
    // Clipboard cleanup is best effort and must not surface the copied value.
  }
}

export function createCopyProxyCredentialsHandler(dependencies: ProxyCredentialDependencies) {
  const schedule = dependencies.schedule ?? setTimeout

  return async (event: InvokeEvent, value: unknown): Promise<{ copied: true }> => {
    if (
      event.sender.id !== dependencies.allowedSenderId
      || event.senderFrame === null
      || event.senderFrame !== event.sender.mainFrame
    ) {
      throw new Error('credential copy is not allowed')
    }
    validateRequest(value)
    const status = dependencies.getSidecarStatus()
    if (status.state !== 'ready') throw new Error('credential service is unavailable')

    let response: Response
    try {
      response = await dependencies.request(internalEndpoint(status), {
        method: 'POST',
        cache: 'no-store',
        redirect: 'error',
        signal: AbortSignal.timeout(10_000),
        headers: {
          accept: 'application/json',
          'content-type': 'application/json',
          'x-autoflow-host-token': status.hostToken,
        },
        body: JSON.stringify({
          proxy_id: value.proxyId,
          protocol: value.protocol,
          format: value.format,
        }),
      })
    } catch {
      throw new Error('credential copy failed')
    }
    if (!response.ok) throw new Error('credential copy failed')
    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new Error('credential copy failed')
    }
    if (!body || typeof body !== 'object' || typeof (body as Record<string, unknown>).value !== 'string') {
      throw new Error('credential copy failed')
    }

    const copiedValue = (body as { value: string }).value
    try {
      dependencies.clipboard.writeText(copiedValue)
    } catch {
      throw new Error('credential copy failed')
    }
    schedule(() => { void clearIfUnchanged(dependencies.clipboard, copiedValue) }, 30_000)
    return { copied: true }
  }
}
