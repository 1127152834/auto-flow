import { mockRequest } from './mock-server'

/** Single IO seam for migrated requests. No mutation of global fetch. */
export type StudioTransport = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
let transport: StudioTransport = mockRequest
export function setStudioTransport(next: StudioTransport): () => void {
  const previous = transport
  transport = next
  return () => { transport = previous }
}
export const studioFetch: StudioTransport = async (input, init) => {
  try {
    return await transport(input, init)
  } catch (error) {
    if (!init?.signal?.aborted && error instanceof TypeError && /fetch|network/i.test(error.message)) {
      window.dispatchEvent(new CustomEvent('studio:connection-error'))
    }
    throw error
  }
}
