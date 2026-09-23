import { afterEach, expect, it, vi } from 'vitest'
import { apiRequest, recorderApi, variableTrackingApi, workflowApi } from '../api'
import { configureStudioConnection } from '../api/config'

afterEach(() => vi.unstubAllGlobals())

it('binds run and debug requests to the host project without saving the draft', async () => {
  vi.stubGlobal('location', { search: '?projectId=host-project' })
  const transport = vi.fn(async () => Response.json({ runId: 'run', status: 'starting' }))
  const restore = configureStudioConnection('http://project-run.test', transport)
  const document = { id: 'draft', nodes: [], edges: [], variables: [] }
  try {
    for (const debug of [false, true]) await workflowApi.execute('draft', { runId: 'run', documentId: 'draft', projectId: 'other', document, debug })
    expect(transport).toHaveBeenCalledTimes(2)
    for (const call of vi.mocked(transport).mock.calls as unknown as [string, RequestInit][]) {
      expect(call[0]).toBe('http://project-run.test/api/workflows/draft/execute?projectId=host-project')
      expect(JSON.parse(call[1].body as string)).toEqual(expect.objectContaining({ projectId: 'host-project', document }))
    }
    expect(document).not.toHaveProperty('projectId')
  } finally { restore() }
})

it('scopes run history, results, diagnostics and downloads to the host project', async () => {
  vi.stubGlobal('location', { search: '?projectId=host-project' })
  const urls: string[] = []
  const restore = configureStudioConnection('http://project-run.test', async input => {
    urls.push(String(input))
    return Response.json({ runId: 'run', items: [], total: 0, nextCursor: null, throughSequence: 0, tracking: [] })
  })
  try {
    await workflowApi.listRuns('doc')
    await workflowApi.getRun('run')
    await workflowApi.getRunLogs('run')
    await workflowApi.getRunResults('run')
    await workflowApi.exportRunLogs('run')
    await workflowApi.exportRunResults('run', 0)
    await variableTrackingApi.exportRun('run', 0)
    await variableTrackingApi.clearRun('run')
    await apiRequest('/workflow-runs/run?projectId=other')
    expect(urls).toHaveLength(9)
    for (const url of urls) expect(new URL(url).searchParams.get('projectId')).toBe('host-project')
    expect(new URL(urls[0]).searchParams.get('documentId')).toBe('doc')
  } finally { restore() }
})

it('keeps control, interaction queries and lost command replies on the host project', async () => {
  vi.stubGlobal('location', { search: '?projectId=host-project' })
  const urls: string[] = []
  const restore = configureStudioConnection('http://project-run.test', async input => {
    urls.push(String(input))
    return Response.json({ error: { message: '受控失败' } }, { status: 503 })
  })
  try {
    const context = { runId: 'run', pauseId: 'pause', controlRevision: 1, commandId: 'command' }
    await workflowApi.stop('flow', 'run')
    await workflowApi.debugResume('flow', context)
    await workflowApi.debugStep('flow', context)
    await workflowApi.debugVariables('flow', { ...context, changes: [{ name: 'answer', value: 42 }] })
    for (const type of ['input-prompts', 'js-requests', 'tts-requests', 'desktop-actions']) await apiRequest(`/events/${type}/request`)
    expect(urls).toHaveLength(11)
    expect(urls.filter(url => new URL(url).pathname === '/api/events/commands/command')).toHaveLength(3)
    for (const url of urls) expect(new URL(url).searchParams.get('projectId')).toBe('host-project')
  } finally { restore() }
})


it('scopes browser, picker and recording history, and freezes the recording document', async () => {
  vi.stubGlobal('location', { search: '?projectId=host-project' })
  const urls: string[] = []
  const bodies: unknown[] = []
  const restore = configureStudioConnection('http://project-run.test', async (input, init) => {
    urls.push(String(input))
    if (init?.body) bodies.push(JSON.parse(String(init.body)))
    return Response.json({ success: true, sessionId: 'recording', recording: true, nextSeq: 0 })
  })
  try {
    for (const path of ['/browser/status', '/browser/pages', '/element-picker/result?sessionId=picker', '/recorder/status', '/recorder/commands/id', '/recorder/reviews/draft']) {
      await apiRequest(`${path}${path.includes('?') ? '&' : '?'}projectId=other`)
    }
    await recorderApi.start('recording', 'unsaved-document')
    expect(urls).toHaveLength(7)
    for (const url of urls) expect(new URL(url).searchParams.get('projectId')).toBe('host-project')
    expect(bodies).toEqual([{ sessionId: 'recording', commandId: expect.any(String), documentId: 'unsaved-document' }])
  } finally { restore() }
})
