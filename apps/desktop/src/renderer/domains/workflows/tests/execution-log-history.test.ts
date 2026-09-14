import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'] as const)('execution log history protocol: %s', mode => {
  let fixture: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let server: typeof import('../api/mock-server')
  let request: (path: string, init?: RequestInit) => Promise<Response>

  beforeEach(async () => {
    const data = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => data.set(key, value),
      removeItem: (key: string) => data.delete(key),
    })
    vi.resetModules()
    server = await import('../api/mock-server')
    if (mode === 'http') {
      fixture = await startHttpStudioFixture(server.mockRequest)
      request = (path, init) => fetch(`${fixture!.origin}/api${path}`, init)
    } else request = (path, init) => server.mockRequest(`http://autoflow-studio.mock/api${path}`, init)
  })

  afterEach(async () => {
    await fixture?.close()
    fixture = undefined
    vi.unstubAllGlobals()
  })

  it('pages, filters and exports all 10,000 persisted logs without duplicates', async () => {
    server.seedMockRunHistory({
      runId: 'run-capacity', workflowId: 'workflow-shared', documentId: 'document-capacity',
      logs: Array.from({ length: 10_000 }, (_, index) => ({
        id: `log-${index + 1}`,
        timestamp: new Date(Date.UTC(2026, 8, 14, 0, 0, index)).toISOString(),
        level: index % 100 === 0 ? 'error' as const : 'info' as const,
        nodeId: `node-${(index % 7) + 1}`,
        message: `${index % 100 === 0 ? '故障' : '调度'}-${String(index + 1).padStart(5, '0')}`,
      })),
    })

    const newest = await (await request('/workflow-runs/run-capacity/logs?cursor=0&limit=500')).json()
    const older = await (await request('/workflow-runs/run-capacity/logs?cursor=500&limit=500')).json()
    expect(newest).toMatchObject({ runId: 'run-capacity', workflowId: 'workflow-shared', total: 10_000, nextCursor: 500 })
    expect(newest.items[0].sequence).toBe(9501)
    expect(newest.items.at(-1).sequence).toBe(10_000)
    expect(older.items[0].sequence).toBe(9001)
    expect(older.items.at(-1).sequence).toBe(9500)
    expect(new Set([...older.items, ...newest.items].map(item => item.id)).size).toBe(1000)

    const filtered = await (await request('/workflow-runs/run-capacity/logs?query=%E6%95%85%E9%9A%9C&levels=error&nodeId=node-1&limit=500')).json()
    expect(filtered.items.length).toBe(filtered.total)
    expect(filtered.items.every((item: { level: string; nodeId: string; message: string }) => item.level === 'error' && item.nodeId === 'node-1' && item.message.startsWith('故障-'))).toBe(true)

    const exported = await request('/workflow-runs/run-capacity/logs/export')
    expect(exported.headers.get('content-type')).toContain('application/x-ndjson')
    const lines = (await exported.text()).trim().split('\n')
    expect(lines).toHaveLength(10_000)
    expect(JSON.parse(lines[0])).toMatchObject({ runId: 'run-capacity', sequence: 1, id: 'log-1' })
    expect(JSON.parse(lines.at(-1)!)).toMatchObject({ sequence: 10_000, id: 'log-10000' })
  }, 20_000)

  it('lists independent runs and rejects invalid queries explicitly', async () => {
    for (const runId of ['run-a', 'run-b']) server.seedMockRunHistory({ runId, workflowId: 'same-workflow', documentId: 'same-document', logs: [] })
    const history = await (await request('/workflow-runs?documentId=same-document&limit=20')).json()
    expect(history.items.map((item: { runId: string }) => item.runId).sort()).toEqual(['run-a', 'run-b'])
    expect(history.total).toBe(2)
    for (const path of [
      '/workflow-runs/run-a/logs?cursor=-1',
      '/workflow-runs/run-a/logs?limit=501',
      '/workflow-runs/run-a/logs?levels=verbose',
      '/workflow-runs?cursor=0.5',
    ]) expect((await request(path)).status).toBe(422)
    expect((await request('/workflow-runs/missing/logs')).status).toBe(404)
  })

  it('uses a stable run ID to prevent duplicate starts and separate repeated workflow runs', async () => {
    const json = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })
    await request('/workflows', json({ id: 'same-workflow', name: '重复运行', nodes: [{ id: 'only', type: 'open_page', data: {} }], edges: [] }))
    const firstRequest = { runId: 'stable-run-1', documentId: 'document-repeat', headless: false }
    expect((await request('/workflows/same-workflow/execute', json(firstRequest))).status).toBe(200)
    expect((await request('/workflows/same-workflow/execute', json(firstRequest))).status).toBe(200)
    expect((await request('/workflows/same-workflow/execute', json({ ...firstRequest, headless: true }))).status).toBe(409)
    await vi.waitFor(() => expect(server.mockSnapshot().run).toBeNull(), { timeout: 1500 })
    expect((await request('/workflows/same-workflow/execute', json({ runId: 'stable-run-2', documentId: 'document-repeat' }))).status).toBe(200)
    await vi.waitFor(() => expect(server.mockSnapshot().run).toBeNull(), { timeout: 1500 })
    const history = await (await request('/workflow-runs?documentId=document-repeat')).json()
    expect(history.items.map((item: { runId: string }) => item.runId).sort()).toEqual(['stable-run-1', 'stable-run-2'])
    expect((await (await request('/workflow-runs/stable-run-1/logs')).json()).total).toBe(1)
    expect((await (await request('/workflow-runs/stable-run-2/logs')).json()).total).toBe(1)
  })
})
