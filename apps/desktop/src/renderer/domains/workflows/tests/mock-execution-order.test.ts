import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startHttpStudioFixture } from './fixtures/http-studio-server'
import { parseServerSentEvents } from '../../../shared/api/events'

describe.each(['memory', 'http'])('explicit execution fixture over %s', mode => {
  let server: typeof import('../api/mock-server')
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let request: (path: string, body?: unknown) => Promise<Response>
  beforeEach(async () => {
    const storage = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value) })
    vi.resetModules(); server = await import('../api/mock-server')
    if (mode === 'http') fixture = await startHttpStudioFixture(server.mockRequest)
    request = (path, body) => {
      const init = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      return fixture ? fetch(`${fixture.origin}/api${path}`, init) : server.mockRequest(`http://autoflow-studio.mock/api${path}`, init)
    }
  })
  afterEach(async () => {
    const active = server.mockSnapshot().run
    if (active) await request(`/workflows/${active}/stop`, {})
    server.configureMock({ disconnect: true, executionOrder: null }); await fixture?.close(); fixture = undefined; vi.unstubAllGlobals()
  })
  const document = { id: 'trace', name: '分支重复事件夹具', nodes: [
    { id: 'false', type: 'click_element' }, { id: 'extract', type: 'get_element_info' }, { id: 'open', type: 'open_page' }, { id: 'true', type: 'click_element' },
  ], variables: [] }
  async function events() {
    const count = server.mockSnapshot().sequence
    const response = await request('/events/stream?afterSeq=0')
    const iterator = parseServerSentEvents(response.body!)[Symbol.asyncIterator]()
    const result: Array<{ event: string; data: { nodeId?: string; node_id?: string; log?: { message: string } } }> = []
    try {
      for (let i=0; i<count; i++) { const item=(await iterator.next()).value!; result.push({ event:item.event, data:JSON.parse(item.data) }) }
    } finally { await iterator.return?.(undefined); await response.body?.cancel() }
    return result
  }
  it('freezes a chosen branch and repeated results instead of visiting node array order', async () => {
    await request('/workflows', document)
    const order = ['open', 'true', 'extract', 'extract']
    server.configureMock({ executionOrder: order })
    expect((await request('/workflows/trace/execute', {})).status).toBe(200)
    order[0] = 'false'; server.configureMock({ executionOrder: ['false'] })
    await vi.waitFor(() => expect(server.mockSnapshot().run).toBeNull(), { timeout: 3000 })
    const journal = await events()
    expect(journal.filter(e=>e.event==='execution:node_start').map(e=>e.data.nodeId)).toEqual(['open','true','extract','extract'])
    expect(journal.filter(e=>e.event==='execution:node_complete')).toHaveLength(4)
    const rows = await (await request('/workflows/trace/data/full')).json()
    expect(rows.rows).toMatchObject([{nodeId:'extract',index:3},{nodeId:'extract',index:4}])
    expect(journal.filter(e=>e.event==='execution:log').map(e=>e.data.log?.message)).toEqual(expect.arrayContaining([expect.stringContaining('第 3 次调度'),expect.stringContaining('第 4 次调度')]))
  })
  it('rejects stale fixture node identities before starting or emitting events', async () => {
    await request('/workflows', document)
    server.configureMock({ executionOrder: ['deleted'] })
    expect((await request('/workflows/trace/execute', {})).status).toBe(422)
    expect(server.mockSnapshot()).toMatchObject({run:null,sequence:0})
  })
  it('pauses and steps each visit, including a repeated breakpoint', async () => {
    await request('/workflows', document)
    server.configureMock({ executionOrder: ['open','extract','open'] })
    await request('/workflows/trace/execute', {breakpoints:['open']})
    await vi.waitFor(async () => expect((await events()).filter(e=>e.event==='execution:paused')).toHaveLength(1))
    await request('/workflows/trace/debug/step', {commandId:crypto.randomUUID(),...server.mockSnapshot().pause})
    await vi.waitFor(async () => expect((await events()).filter(e=>e.event==='execution:paused')).toHaveLength(2))
    expect((await events()).filter(e=>e.event==='execution:node_start').map(e=>e.data.nodeId)).toEqual(['open'])
    await request('/workflows/trace/debug/resume', {commandId:crypto.randomUUID(),...server.mockSnapshot().pause})
    await vi.waitFor(async () => expect((await events()).filter(e=>e.event==='execution:paused')).toHaveLength(3))
    expect((await events()).filter(e=>e.event==='execution:paused').map(e=>e.data.node_id)).toEqual(['open','extract','open'])
    await request('/workflows/trace/debug/resume', {commandId:crypto.randomUUID(),...server.mockSnapshot().pause})
    await vi.waitFor(() => expect(server.mockSnapshot().run).toBeNull(), {timeout:2000})
  })
  it('runs the real prefix once and pauses before the temporary target', async () => {
    await request('/workflows', document)
    server.configureMock({ executionOrder: ['open', 'extract', 'true'] })
    await request('/workflows/trace/execute', {runToNodeId:'extract'})
    await vi.waitFor(async () => expect((await events()).filter(e=>e.event==='execution:paused')).toHaveLength(1))
    const journal = await events()
    expect(journal.filter(e=>e.event==='execution:node_start').map(e=>e.data.nodeId)).toEqual(['open'])
    expect(journal.find(e=>e.event==='execution:paused')).toMatchObject({data:{node_id:'extract'}})
    await request('/workflows/trace/debug/resume', {commandId:crypto.randomUUID(),...server.mockSnapshot().pause})
    await vi.waitFor(() => expect(server.mockSnapshot().run).toBeNull(), {timeout:2000})
    expect((await events()).filter(e=>e.event==='execution:paused')).toHaveLength(1)
  })
})
