import { createServer, type ServerResponse } from 'node:http'
import { once } from 'node:events'
import type { StudioTransport } from '../../api/transport'

/** Loopback-only test adapter for the same stateful fixture; no browser actions or external proxy. */
export async function startHttpStudioFixture(handler: StudioTransport) {
  const responses = new Set<ServerResponse>()
  let cancelledStreams = 0
  const server = createServer(async (request, response) => {
    const abort = new AbortController()
    responses.add(response)
    response.on('close', () => { abort.abort(); responses.delete(response) })
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
    try {
      if (!request.url?.startsWith('/api/')) { response.writeHead(404).end(); return }
      const chunks: Buffer[] = []
      for await (const chunk of request) chunks.push(Buffer.from(chunk))
      const bytes = Buffer.concat(chunks)
      const headers = new Headers()
      for (const [key, value] of Object.entries(request.headers)) if (value !== undefined) headers.set(key, Array.isArray(value) ? value.join(', ') : value)
      const result = await handler(new Request(`http://autoflow-studio.mock${request.url}`, {
        method: request.method, headers, ...(bytes.length ? { body: bytes } : {}), signal: abort.signal,
      }))
      response.writeHead(result.status, Object.fromEntries(result.headers.entries()))
      response.flushHeaders()
      if (!result.body) { response.end(); return }
      const stream = result.headers.get('content-type')?.includes('text/event-stream')
      reader = result.body.getReader()
      abort.signal.addEventListener('abort', () => {
        if (stream) cancelledStreams++
        void reader?.cancel().catch(() => {})
      }, { once: true })
      while (!abort.signal.aborted) {
        const next = await reader.read()
        if (next.done) break
        // Deliberately split UTF-8/SSE delimiters across writes to exercise incremental consumers.
        const size = stream ? 7 : next.value.length
        for (let offset = 0; offset < next.value.length && !abort.signal.aborted; offset += size) {
          if (!response.write(next.value.subarray(offset, offset + size))) await once(response, 'drain', { signal: abort.signal })
        }
      }
      response.end()
    } catch {
      response.destroy()
    } finally {
      reader?.releaseLock()
    }
  })
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const address = server.address()
  if (!address || typeof address === 'string') throw new Error('Expected a loopback port')
  return {
    origin: `http://127.0.0.1:${address.port}`,
    get cancelledStreams() { return cancelledStreams },
    async close() {
      for (const response of responses) response.destroy()
      await new Promise<void>((resolve, reject) => { server.close(error => error ? reject(error) : resolve()); server.closeAllConnections() })
    },
  }
}
