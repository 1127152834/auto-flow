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
  const reference = within(await screen.findByRole('form', { name: '拉取镜像' })).getByLabelText('拉取镜像引用')
  expect(reference).toHaveAttribute('placeholder', 'redroid/redroid:13 或 redroid/redroid@sha256:…')
  await userEvent.type(reference, 'redroid/redroid:13')
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

it('separates image metadata verification from Google component validation', async () => {
  renderManager({ images: vi.fn(async () => ({ items: [{ ...image, state: 'verified', googleComponents: 'detected', verification: { state: 'passed', records: [] }, validation: 'not_tested' }], nextCursor: null, total: 1 })) })

  expect(await screen.findByText(/镜像元数据核验 通过/)).toBeVisible()
  expect(screen.getByText(/谷歌组件验收 未测试/)).toBeVisible()
  expect(screen.getByText(/组件声明 detected/)).toBeVisible()
})


it.each([false, true])('explicitly reconciles an unknown pull using its original request id, retry=%s', async (retry) => {
  const unknown = { operationId: 'pull-op', targetId: 'synthetic-pull-target', action: 'pull', state: 'needs_verification', stageCode: 'verify', stageLabel: '待核实', attempt: 1, createdAt: '', allowedActions: ['verify'] }
  const pullImage = vi.fn(async (body: { requestId: string }) => ({ ...unknown, requestId: body.requestId }))
  const operationByRequest = vi.fn(async (requestId: string) => ({ ...unknown, requestId }))
  const verify = vi.fn().mockImplementation(async (_id: string, body: { requestId: string }) => ({ ...unknown, ...body, state: 'succeeded', stageLabel: '已完成' }))
  if (retry) verify.mockRejectedValueOnce(new Error('暂时无法核实'))
  const api = renderManager({ pullImage, operationByRequest, verify })
  await userEvent.type(within(await screen.findByRole('form', { name: '拉取镜像' })).getByLabelText('拉取镜像引用'), 'redroid/redroid:13')
  await userEvent.click(screen.getByRole('button', { name: '开始拉取' }))
  const requestId = pullImage.mock.calls[0][0].requestId
  await userEvent.click(screen.getByRole('button', { name: '按原编号核实拉取' }))
  await vi.waitFor(() => expect(verify).toHaveBeenCalledWith('pull-op', { requestId }))
  if (retry) {
    expect(await screen.findByRole('alert')).toHaveTextContent('暂时无法核实')
    expect(within(screen.getByRole('form', { name: '拉取镜像' })).getByRole('status')).toHaveTextContent('needs_verification')
    await userEvent.click(screen.getByRole('button', { name: '按原编号重试' }))
  }
  await vi.waitFor(() => expect(within(screen.getByRole('form', { name: '拉取镜像' })).getByRole('status')).toHaveTextContent('已完成'))
  expect(verify).toHaveBeenCalledTimes(retry ? 2 : 1)
  expect(verify).toHaveBeenLastCalledWith('pull-op', { requestId })
  expect(operationByRequest).toHaveBeenLastCalledWith(requestId)
  expect(pullImage).toHaveBeenCalledTimes(1)
  expect(api.images).toHaveBeenCalledTimes(2)
  expect(api.verifyImage).not.toHaveBeenCalled()
  if (!retry) {
    await userEvent.click(screen.getByRole('button', { name: '开始拉取' }))
    expect(pullImage.mock.calls[1][0].requestId).not.toBe(requestId)
  }
})

it('keeps the second pull identity after a lost response instead of verifying the previous success', async () => {
  const unknown = (requestId: string) => ({ operationId: `op-${requestId}`, requestId, targetId: 'pull-target', action: 'pull', state: 'needs_verification', stageCode: 'verify', stageLabel: '待核实', attempt: 1, createdAt: '', allowedActions: ['verify'] })
  const completed = new Set<string>()
  const pullImage = vi.fn().mockImplementationOnce(async (body: { requestId: string }) => unknown(body.requestId)).mockRejectedValueOnce(new Error('第二次拉取响应丢失'))
  const operationByRequest = vi.fn(async (requestId: string) => ({ ...unknown(requestId), ...(completed.has(requestId) ? { state: 'succeeded', stageLabel: '已完成' } : {}) }))
  let failedVerification = false
  const verify = vi.fn(async (_id: string, body: { requestId: string }) => {
    if (completed.size && !failedVerification) { failedVerification = true; throw new Error('第二次核实暂不可用') }
    completed.add(body.requestId)
    return { ...unknown(body.requestId), state: 'succeeded', stageLabel: '已完成' }
  })
  renderManager({ pullImage, operationByRequest, verify })
  await userEvent.type(within(await screen.findByRole('form', { name: '拉取镜像' })).getByLabelText('拉取镜像引用'), 'redroid/redroid:13')
  await userEvent.click(screen.getByRole('button', { name: '开始拉取' }))
  const first = pullImage.mock.calls[0][0].requestId
  await userEvent.click(screen.getByRole('button', { name: '按原编号核实拉取' }))
  await vi.waitFor(() => expect(completed.has(first)).toBe(true))
  await userEvent.click(screen.getByRole('button', { name: '开始拉取' }))
  const second = pullImage.mock.calls[1][0].requestId
  expect(second).not.toBe(first)
  expect(await screen.findByRole('alert')).toHaveTextContent('第二次拉取响应丢失')
  await userEvent.click(screen.getByRole('button', { name: '按原编号核实拉取' }))
  expect(operationByRequest).toHaveBeenLastCalledWith(second)
  expect(await screen.findByRole('alert')).toHaveTextContent('第二次核实暂不可用')
  expect(verify).toHaveBeenLastCalledWith(`op-${second}`, { requestId: second })
  await userEvent.click(screen.getByRole('button', { name: '按原编号重试' }))
  await vi.waitFor(() => expect(completed.has(second)).toBe(true))
  expect(operationByRequest).toHaveBeenLastCalledWith(second)
  expect(verify).toHaveBeenLastCalledWith(`op-${second}`, { requestId: second })
  expect(pullImage).toHaveBeenCalledTimes(2)
})
