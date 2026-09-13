import { normalizeStudioOrigin } from './config'
import type { StudioTransport } from './transport'

/** AutoFlow-owned authentication, scoped to one sidecar origin. No token storage or URL credentials. */
export function createStudioHttpTransport(origin: string, token: string, fetcher: StudioTransport = fetch): StudioTransport {
  const allowedOrigin = normalizeStudioOrigin(origin)
  if (!token.trim()) throw new Error('Studio HTTP transport requires an AutoFlow service token')
  return async (input, init) => {
    const request = new Request(input, init)
    if (new URL(request.url).origin !== allowedOrigin) throw new Error('Studio request does not belong to the configured service')
    const headers = new Headers(request.headers)
    headers.delete('X-WebRPA-Token')
    headers.set('X-AutoFlow-Token', token)
    // Custom token headers are not reliably stripped across redirects. Reject redirects entirely.
    return fetcher(new Request(request, { headers, redirect: 'error', credentials: 'omit' }))
  }
}
