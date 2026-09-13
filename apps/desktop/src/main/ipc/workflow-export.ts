import { randomUUID } from 'node:crypto'
import { createWriteStream } from 'node:fs'
import { rename, rm } from 'node:fs/promises'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import type { DesktopRuntimeContext, WorkflowExportRequest } from '../../shared/runtime'
import type { DesktopIpcEvent } from './automation-studio'

export function createWorkflowExportHandler(options: {
  allowed(event: DesktopIpcEvent): boolean
  context(): DesktopRuntimeContext
  selectPath(name: string): Promise<string | null>
  request: typeof fetch
}) {
  return async (event: DesktopIpcEvent, input: WorkflowExportRequest): Promise<{ saved: boolean }> => {
    if (!options.allowed(event)) throw new Error('此窗口不能导出工作流记录')
    if (!input || typeof input !== 'object' || !/^[a-f0-9-]{36}$/i.test(input.runId) || !['logs', 'results', 'diagnostics'].includes(input.kind) || !Number.isSafeInteger(input.throughSeq) || input.throughSeq < 0) throw new Error('无效的导出请求')
    const context = options.context()
    if (context.workspaceKey !== input.workspaceKey || context.sidecar.state !== 'ready') throw new Error('工作区或连接已变化')
    const filters = input.filters ?? {}
    if (Object.entries(filters).some(([key, value]) => !['q', 'level', 'nodeId', 'executionId'].includes(key) || typeof value !== 'string' || value.length > 2000)) throw new Error('无效的日志筛选')
    const extension = input.kind === 'results' ? 'zip' : input.kind === 'logs' ? 'jsonl' : 'json'
    const target = await options.selectPath(`${input.runId}-${input.kind}.${extension}`)
    if (!target) return { saved: false }
    const current = options.context()
    if (current.workspaceKey !== context.workspaceKey || current.sidecar.state !== 'ready' || current.sidecar.instanceId !== context.sidecar.instanceId) throw new Error('工作区或连接已变化，请重新导出')
    const partial = `${target}.${randomUUID()}.partial`
    const response = await options.request(`${context.sidecar.baseUrl}/api/v1/workflows/runs/${input.runId}/export?${new URLSearchParams({ ...filters, kind: input.kind, throughSeq: String(input.throughSeq) })}`, { headers: { 'x-autoflow-token': context.sidecar.token }, redirect: 'error', signal: AbortSignal.timeout(300000) })
    if (!response.ok || !response.body) throw new Error('导出失败，请检查记录和产物是否仍然可用')
    try {
      await pipeline(Readable.fromWeb(response.body as import('node:stream/web').ReadableStream), createWriteStream(partial, { flags: 'wx' }))
      await rename(partial, target)
      return { saved: true }
    } finally { await rm(partial, { force: true }) }
  }
}
