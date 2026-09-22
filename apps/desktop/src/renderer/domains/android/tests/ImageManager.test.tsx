import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiClientError } from '../../../shared/api/client'
import { ImageManager } from '../components/ImageManager'
import type { AndroidManagementApi } from '../management-api'

afterEach(cleanup)

const image = {
  id: 'image-1',
  imageId: `sha256:${'a'.repeat(64)}`,
  name: 'Android 13',
  reference: 'redroid:13',
  revision: 1,
  state: 'registered',
  verification: { state: 'not_tested', records: [] },
  createdAt: '2026-09-22T00:00:00Z',
  references: [],
}

function renderManager(overrides: Record<string, unknown> = {}) {
  const api = {
    images: vi.fn(async () => ({ items: [image], nextCursor: null, total: 1 })),
    registerImage: vi.fn(async () => image),
    pullImage: vi.fn(async (body: { requestId: string }) => ({ operationId: 'op-1', requestId: body.requestId, targetId: 'image-1', action: 'pull', state: 'running', stageCode: 'pulling', stageLabel: '正在拉取', attempt: 1, createdAt: '' })),
    operationByRequest: vi.fn(async () => ({ operationId: 'op-1', requestId: 'pull-1', targetId: 'image-1', action: 'pull', state: 'succeeded', stageCode: 'complete', stageLabel: '已完成', attempt: 1, createdAt: '' })),
    deleteImage: vi.fn(async () => ({ ...image, state: 'unregistered' })),
    verifyImage: vi.fn(async () => ({ ...image, verification: { state: 'passed', records: [{ check: 'boot', result: 'passed' }] } })),
    ...overrides,
  } as unknown as AndroidManagementApi
  render(<QueryClientProvider client={new QueryClient()}><ImageManager api={api} /></QueryClientProvider>)
  return api
}

it('registers a fixed digest and keeps the exact reference', async () => {
  const api = renderManager()
  const form = await screen.findByRole('form', { name: '登记镜像' })
  await userEvent.type(within(form).getByLabelText('镜像名称'), 'Android 13')
  await userEvent.type(within(form).getByLabelText('镜像摘要'), `sha256:${'b'.repeat(64)}`)
  await userEvent.type(within(form).getByLabelText('镜像引用'), 'redroid:13')
  await userEvent.click(screen.getByRole('button', { name: '登记镜像' }))
  expect(api.registerImage).toHaveBeenCalledWith({ id: `sha256:${'b'.repeat(64)}`, name: 'Android 13', reference: 'redroid:13' })
})

it('retries a pull with the same request id and can verify by request id', async () => {
  const pullImage = vi.fn().mockRejectedValueOnce(new Error('连接中断')).mockResolvedValueOnce({ operationId: 'op-1', requestId: 'pull-1', targetId: 'image-1', action: 'pull', state: 'running', stageCode: 'pulling', stageLabel: '正在拉取', attempt: 1, createdAt: '' })
  const api = renderManager({ pullImage })
  await userEvent.type(within(await screen.findByRole('form', { name: '拉取镜像' })).getByLabelText('拉取镜像引用'), 'redroid:13')
  await userEvent.click(screen.getByRole('button', { name: '开始拉取' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('连接中断')
  await userEvent.click(screen.getByRole('button', { name: '按原编号重试' }))
  await vi.waitFor(() => expect(pullImage).toHaveBeenCalledTimes(2))
  expect(pullImage.mock.calls[0][0].requestId).toBe(pullImage.mock.calls[1][0].requestId)
  await userEvent.click(screen.getByRole('button', { name: '按原编号核实拉取' }))
  await vi.waitFor(() => expect(api.operationByRequest).toHaveBeenCalledWith(expect.any(String)))
  expect(within(screen.getByRole('form', { name: '拉取镜像' })).getByRole('status')).toHaveTextContent('已完成')
})

it('separates unregister from content deletion and records verification', async () => {
  const api = renderManager()
  await userEvent.click(await screen.findByRole('button', { name: '取消登记 Android 13' }))
  expect(screen.getByRole('button', { name: '确认取消登记' })).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '确认取消登记' }))
  expect(api.deleteImage).toHaveBeenCalledWith('image-1', expect.objectContaining({ deleteContent: false, requestId: expect.any(String) }))
  await userEvent.click(screen.getByRole('button', { name: '删除镜像内容 Android 13' }))
  expect(screen.getByText('删除内容会影响本机镜像缓存')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '确认删除镜像内容' }))
  expect(api.deleteImage).toHaveBeenCalledWith('image-1', expect.objectContaining({ deleteContent: true, requestId: expect.any(String) }))
  await userEvent.click(screen.getByRole('button', { name: '验证 Android 13' }))
  await userEvent.type(screen.getByLabelText('验证检查项'), '启动')
  await userEvent.click(screen.getByRole('button', { name: '服务端核实' }))
  expect(api.verifyImage).toHaveBeenCalledWith('image-1', expect.objectContaining({ check: '启动' }))
})

it('核实未知的镜像内容删除结果而不重复删除', async () => {
  const deleteImage = vi.fn(async () => { throw new ApiClientError('删除结果未知', 503, 'ANDROID_IMAGE_DELETE_RESULT_UNKNOWN') })
  const verifyImageDelete = vi.fn(async () => ({ ...image, state: 'deleted' }))
  renderManager({ deleteImage, verifyImageDelete })
  await userEvent.click(await screen.findByRole('button', { name: '删除镜像内容 Android 13' }))
  await userEvent.click(screen.getByRole('button', { name: '确认删除镜像内容' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('删除结果未知')
  await userEvent.click(screen.getByRole('button', { name: '核实删除结果' }))
  expect(verifyImageDelete).toHaveBeenCalledWith('image-1', expect.objectContaining({ requestId: expect.any(String) }))
  expect(deleteImage).toHaveBeenCalledTimes(1)
})
