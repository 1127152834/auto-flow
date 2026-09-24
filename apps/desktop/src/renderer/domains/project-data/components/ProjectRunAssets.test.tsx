import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { createProjectRunAssetsApi, type RunAsset } from '../run-assets-api'
import { ProjectRunAssets } from './ProjectRunAssets'

choiceTestEnvironment()
afterEach(() => { cleanup(); vi.restoreAllMocks() })
const asset: RunAsset = { assetId: 'result:run:2', projectId: 'p', runId: 'run', workflowId: 'flow', workflowName: '网页采集', kind: 'result', sequence: 2, nodeId: 'extract', executionId: 'iteration-2', createdAt: '2026-09-23T00:00:00Z', artifactId: null, mimeType: 'application/json', size: null, sha256: null }
const row = { sequence: 2, nodeId: 'extract', executionId: 'iteration-2', values: { answer: '真实读取结果' }, executionContext: { loop: 2 }, largeValues: {} }
function mount(client: StreamingApiClient) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = (projectId = 'p', instanceId = 'i') => <QueryClientProvider client={cache}><ProjectRunAssets workspaceKey="w" instanceId={instanceId} projectId={projectId} client={client} disabled={false} /></QueryClientProvider>
  const view = render(tree())
  return { ...view, changeProject: () => view.rerender(tree('other')), changeInstance: () => view.rerender(tree('p', 'new')) }
}
function api(request: (path: string) => Promise<unknown>, stream = vi.fn()): StreamingApiClient {
  return { request: vi.fn(request) as StreamingApiClient['request'], stream, health: vi.fn() }
}
it('pages and filters registered facts through the project API, then reads result and node logs', async () => {
  const client = api(async path => path.includes('/results/') ? row : path.includes('/logs?') ? { items: [{ sequence: 3, message: '第二轮完成' }], total: 1, nextCursor: null } : { items: [asset], total: 60, nextCursor: 50 })
  mount(client)
  await userEvent.click(await screen.findByRole('button', { name: '下一页' }))
  await waitFor(() => expect(client.request).toHaveBeenCalledWith(expect.stringContaining('cursor=50'), expect.anything()))
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '运行数据类型' }), 'diagnostic')
  await waitFor(() => expect(client.request).toHaveBeenLastCalledWith(expect.stringContaining('cursor=0&limit=50&kind=diagnostic'), expect.anything()))
  await userEvent.click(screen.getByRole('button', { name: `预览 ${asset.assetId}` }))
  expect(await screen.findByText(/真实读取结果/)).toBeVisible()
  expect(client.request).toHaveBeenCalledWith('/api/workflow-runs/run/results/2?projectId=p', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  await userEvent.click(screen.getByRole('button', { name: `日志 ${asset.assetId}` }))
  expect(await screen.findByText(/第二轮完成/)).toBeVisible()
  expect(client.request).toHaveBeenCalledWith('/api/workflow-runs/run/logs?projectId=p&nodeId=extract&executionId=iteration-2&cursor=0&limit=100', expect.anything())
})
it('rejects foreign project rows instead of displaying cached or returned content', async () => {
  mount(api(async () => ({ items: [{ ...asset, projectId: 'other' }], total: 1, nextCursor: null })))
  expect(await screen.findByRole('alert')).toHaveTextContent('运行数据不属于当前项目')
  expect(screen.queryByRole('button', { name: `预览 ${asset.assetId}` })).not.toBeInTheDocument()
})
it('shows a missing artifact error and does not fake an empty preview', async () => {
  const image = { ...asset, kind: 'file' as const, artifactId: 'png', mimeType: 'image/png', size: 3 }
  mount(api(async () => ({ items: [image], total: 1, nextCursor: null }), vi.fn().mockRejectedValue(new ApiClientError('运行产物文件缺失', 404, 'ARTIFACT_FILE_MISSING'))))
  await userEvent.click(await screen.findByRole('button', { name: `预览 ${asset.assetId}` }))
  expect(await screen.findByRole('alert')).toHaveTextContent('运行产物文件缺失')
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})
it('revokes image URLs and clears content on project change', async () => {
  const image = { ...asset, kind: 'file' as const, artifactId: 'png', mimeType: 'image/png', size: 3 }
  const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:preview')
  const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  const client = api(async path => ({ items: path.includes('/projects/p/') ? [image] : [], total: 1, nextCursor: null }), vi.fn().mockResolvedValue(new Response('png', { headers: { 'content-type': 'image/png' } })))
  const view = mount(client)
  await userEvent.click(await screen.findByRole('button', { name: `预览 ${asset.assetId}` }))
  expect(await screen.findByRole('img')).toHaveAttribute('src', 'blob:preview')
  expect(create).toHaveBeenCalledOnce()
  view.changeProject()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  expect(revoke).toHaveBeenCalledWith('blob:preview')
})
it('ignores late result reads after a service instance replacement', async () => {
  let resolve!: (value: unknown) => void
  const client = api(async path => path.includes('/results/') ? new Promise(done => { resolve = done }) : { items: [asset], total: 1, nextCursor: null })
  const view = mount(client)
  await userEvent.click(await screen.findByRole('button', { name: `预览 ${asset.assetId}` }))
  view.changeInstance(); resolve(row)
  await waitFor(() => expect(screen.queryByText(/真实读取结果/)).not.toBeInTheDocument())
  expect(screen.queryByRole('region', { name: '运行数据详情' })).not.toBeInTheDocument()
})
it('preserves a large JSON result in the downloadable blob and verifies file size', async () => {
  const client = api(async () => ({ ...row, values: { content: '中'.repeat(70000) } }), vi.fn().mockResolvedValue(new Response('bad')))
  const service = createProjectRunAssetsApi(client, 'p')
  const result = JSON.parse(await (await service.content(asset)).text())
  expect(result.values.content).toBe('中'.repeat(70000))
  await expect(service.content({ ...asset, kind: 'file', artifactId: 'file', size: 99 })).rejects.toThrow('产物大小不一致')
})
