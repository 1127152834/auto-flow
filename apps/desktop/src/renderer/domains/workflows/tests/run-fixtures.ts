import { vi } from 'vitest'
import type { WorkflowRunApi } from '../run-api'
import type { RunEvent, RunRead } from '../run-types'

export function runRecord(overrides: Partial<RunRead> = {}): RunRead {
  return {
    runId: 'run-1', workflowId: 'flow-1', name: '快照流程', profileId: 'profile-1', profileName: '真实配置', state: 'running',
    document: { id: 'flow-1', name: '快照流程', schemaVersion: 1, nodes: [{ id: 'node-1', type: 'open_page', label: '快照节点', config: { url: 'https://example.test', timeoutSeconds: 60 } }], edges: [], variables: [] },
    layout: { nodes: { 'node-1': { x: 0, y: 0 } }, viewport: { x: 0, y: 0, zoom: 1 } },
    profileSnapshot: {}, nodeOrder: ['node-1'], currentNodeId: 'node-1', startedAt: '2026-09-13T00:00:00Z', finishedAt: null,
    latestSeq: 1, completedNodeIds: [], error: null, artifacts: [], warnings: [], ...overrides,
  }
}
export function runEvent(seq: number, overrides: Partial<RunEvent> = {}): RunEvent {
  return { runId: 'run-1', seq, timestamp: '2026-09-13T00:00:00Z', type: 'node_started', nodeId: 'node-1', level: 'info', message: `真实事件 ${seq}`, durationMs: null, artifactId: null, error: null, ...overrides }
}
export function runApi(record: RunRead | null = null): WorkflowRunApi {
  return {
    list: vi.fn(async () => ({ items: record ? [record] : [], activeRunId: record?.state === 'running' ? record.runId : null, nextOffset: null })),
    get: vi.fn(async () => record ?? runRecord()),
    start: vi.fn(async request => runRecord({ ...request, workflowId: request.document.id, name: request.document.name })),
    stop: vi.fn(async () => runRecord({ state: 'cancelled', finishedAt: '2026-09-13T00:00:01Z', latestSeq: 3 })),
    events: vi.fn(async () => ({ items: [runEvent(1)], hasMore: false, nextSeq: 1 })),
    watch: vi.fn((_id, _seq, signal) => new Promise<void>(resolve => signal.addEventListener('abort', () => resolve(), { once: true }))),
    artifact: vi.fn(async () => new Blob(['{"actual":"result"}'], { type: 'application/json' })),
  }
}
