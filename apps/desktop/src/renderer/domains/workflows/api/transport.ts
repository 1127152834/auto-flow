/** Single IO seam for migrated requests. No mutation of global fetch. */
export type StudioTransport = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
let transport: StudioTransport = (input, init) => fetch(input, init)
let transportRevision = 0
let failureRevision = 0
let unavailable = false
export function setStudioTransport(next: StudioTransport): () => void {
  const previous = transport
  transport = next
  transportRevision++
  unavailable = false
  return () => { transport = previous; transportRevision++; unavailable = false }
}
export const studioFetch: StudioTransport = async (input, init) => {
  const origin = transportRevision
  const failures = failureRevision
  try {
    const response = await transport(input, init)
    if (response.ok && unavailable && origin === transportRevision && failures === failureRevision) {
      unavailable = false
      window.dispatchEvent(new CustomEvent('studio:connection-restored'))
    }
    return response
  } catch (error) {
    const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined)
    if (origin === transportRevision && !signal?.aborted && error instanceof TypeError && /fetch|network/i.test(error.message)) {
      unavailable = true
      failureRevision++
      window.dispatchEvent(new CustomEvent('studio:connection-error'))
    }
    throw error
  }
}
