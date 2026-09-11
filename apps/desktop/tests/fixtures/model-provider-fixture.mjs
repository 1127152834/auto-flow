import { createServer } from 'node:http'

// Local, synthetic provider for desktop tests. It never forwards a request.
export async function startModelProviderFixture() {
  const requests = []
  const state = { status: 200, delayMs: 0, models: ['sample-chat', 'sample-reasoner'] }
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1')
    let body = ''
    for await (const chunk of request) {
      body += chunk
      if (body.length > 64 * 1024) {
        response.writeHead(413).end()
        return
      }
    }
    requests.push({ method: request.method, path: url.pathname, authenticated: Boolean(request.headers.authorization), body: body ? JSON.parse(body) : null })
    if (state.delayMs) await new Promise(resolve => setTimeout(resolve, state.delayMs))
    response.setHeader('content-type', 'application/json')
    if (state.status !== 200) {
      response.writeHead(state.status).end(JSON.stringify({ error: { message: 'Synthetic provider error' } }))
    } else if (request.method === 'GET' && url.pathname === '/v1/models') {
      response.end(JSON.stringify({ data: state.models.map(id => ({ id, context_length: 32768 })) }))
    } else if (request.method === 'POST' && url.pathname === '/v1/chat/completions') {
      response.end(JSON.stringify({ choices: [{ message: { content: 'OK', reasoning_content: 'Synthetic reasoning sample' } }] }))
    } else {
      response.writeHead(404).end(JSON.stringify({ error: { message: 'Unknown synthetic endpoint' } }))
    }
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  return {
    baseUrl: `http://127.0.0.1:${server.address().port}/v1`, requests, state,
    close: () => new Promise((resolve, reject) => {
      server.close(error => error ? reject(error) : resolve())
      server.closeAllConnections()
    }),
  }
}
