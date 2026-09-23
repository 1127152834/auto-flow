import { afterEach, expect, it, vi } from 'vitest'
import { apiRequest, variableTrackingApi, workflowApi } from '../api'
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
      expect(call[0]).toBe('http://project-run.test/api/workflows/draft/execute')
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
