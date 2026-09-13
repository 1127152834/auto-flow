import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, expect, it, vi } from 'vitest'
import type { DesktopRuntimeContext, WorkflowExportRequest } from '../../shared/runtime'
import { createWorkflowExportHandler } from './workflow-export'

const directories: string[] = []
afterEach(async () => { for (const path of directories.splice(0)) await rm(path, { recursive: true, force: true }) })
const context: DesktopRuntimeContext = { workspaceKey: '/workspace', operation: 'idle', preferences: { zoom: 100, motion: 'system' }, sidecar: { state: 'ready', apiVersion: 'v1', instanceId: 'instance', port: 123, baseUrl: 'http://127.0.0.1:123', token: 'local-token' } }
const input: WorkflowExportRequest = { workspaceKey: '/workspace', runId: '11111111-1111-4111-8111-111111111111', kind: 'logs', throughSeq: 100 }
const event = { sender: { id: 1, mainFrame: {} }, senderFrame: {} }

it('streams authenticated exports to the selected file and refuses other senders or workspaces', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'm5-export-')); directories.push(directory)
  const target = join(directory, 'log.jsonl')
  const request = vi.fn(async () => new Response('x'.repeat(70000))) as unknown as typeof fetch
  const options = { allowed: () => true, context: () => context, selectPath: async () => target, request }
  expect(await createWorkflowExportHandler(options)(event, input)).toEqual({ saved: true })
  expect((await readFile(target)).length).toBe(70000)
  await expect(createWorkflowExportHandler({ ...options, allowed: () => false })(event, input)).rejects.toThrow('此窗口')
  await expect(createWorkflowExportHandler(options)(event, { ...input, workspaceKey: '/other' })).rejects.toThrow('工作区')
  expect(request).toHaveBeenCalledTimes(1)
  expect(request).toHaveBeenCalledWith(expect.stringContaining('/export?kind=logs&throughSeq=100'), expect.objectContaining({ headers: { 'x-autoflow-token': 'local-token' }, redirect: 'error' }))
})

it('retains an existing user file when the response stream fails and removes the partial file', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'm5-export-')); directories.push(directory)
  const target = join(directory, 'existing.zip'); await writeFile(target, 'original')
  const request = vi.fn(async () => new Response(new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode('partial')); controller.error(new Error('disconnected')) } }))) as unknown as typeof fetch
  const handler = createWorkflowExportHandler({ allowed: () => true, context: () => context, selectPath: async () => target, request })
  await expect(handler(event, input)).rejects.toThrow()
  expect(await readFile(target, 'utf8')).toBe('original')
  expect(await readdir(directory)).toEqual(['existing.zip'])
})
