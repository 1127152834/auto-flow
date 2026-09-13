import { mockRequest } from './mock-server'

/** Single IO seam for migrated requests. No mutation of global fetch. */
export type StudioTransport = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
let transport: StudioTransport = mockRequest
export function setStudioTransport(next: StudioTransport): () => void {
  const previous = transport
  transport = next
  return () => { transport = previous }
}
export const studioFetch: StudioTransport = (input, init) => transport(input, init)
