import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const api = vi.hoisted(() => ({ list: vi.fn(), listFolders: vi.fn() }))
vi.mock('../api', () => ({ imageAssetApi: api }))
import { ImageAssetsPanel } from '../components/ImageAssetsPanel'
import { useWorkflowStore } from '../editor-store'
import { configureStudioConnection } from '../api/config'
const asset = { id: 'kept', name: 'kept.png', originalName: 'kept.png', uploadedAt: '', folder: '', extension: 'png', size: 1, path: null }
let restore = () => {}
beforeEach(() => {
  vi.resetAllMocks()
  api.list.mockResolvedValue({ success: true, data: [asset] })
  api.listFolders.mockResolvedValue({ success: true, data: [] })
  useWorkflowStore.setState({ imageAssets: [asset] })
  restore = configureStudioConnection('http://assets.fixture', async () => Response.json({}))
})
afterEach(() => { cleanup(); restore() })
it.each(['bad-assets', 'bad-folders', 'business-error', 'network-error'])('keeps the last cache and offers retry after %s', async mode => {
  if (mode === 'bad-assets') api.list.mockResolvedValueOnce({ success: true, data: [{ ...asset, size: -1 }] })
  if (mode === 'bad-folders') api.listFolders.mockResolvedValueOnce({ success: true, data: [3] })
  if (mode === 'business-error') api.list.mockResolvedValueOnce({ success: false, data: [], error: '不可用' })
  if (mode === 'network-error') api.list.mockRejectedValueOnce(new Error('离线'))
  render(<ImageAssetsPanel />)
  await screen.findByRole('alert')
  expect(useWorkflowStore.getState().imageAssets).toEqual([asset])
  fireEvent.click(screen.getByRole('button', { name: '重试加载图像资源' }))
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  expect(screen.getByText('kept.png', { exact: true })).toBeTruthy()
})
it('does not let an older refresh replace a newer refresh', async () => {
  let resolve!: (value: unknown) => void
  api.list.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  render(<ImageAssetsPanel />)
  expect(screen.getByText('正在加载图像资源…').textContent).toContain('加载')
  const current = { ...asset, id: 'current', name: 'current.png', originalName: 'current.png' }
  api.list.mockResolvedValue({ success: true, data: [current] })
  act(() => window.dispatchEvent(new Event('refresh:image-assets')))
  await screen.findByText('current.png', { exact: true })
  await act(async () => resolve({ success: true, data: [asset] }))
  expect(useWorkflowStore.getState().imageAssets).toEqual([current])
})
it('does not overwrite a local upload that completed during a pending read', async () => {
  let resolve!: (value: unknown) => void
  api.list.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  render(<ImageAssetsPanel />)
  const uploaded = { ...asset, id: 'uploaded', name: 'uploaded.png', originalName: 'uploaded.png' }
  act(() => useWorkflowStore.getState().addImageAsset(uploaded))
  await act(async () => resolve({ success: true, data: [asset] }))
  expect(useWorkflowStore.getState().imageAssets).toEqual([asset, uploaded])
})
it('does not write a response after the panel unmounts', async () => {
  let resolve!: (value: unknown) => void
  api.list.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  const view = render(<ImageAssetsPanel />)
  view.unmount()
  await act(async () => resolve({ success: true, data: [] }))
  expect(useWorkflowStore.getState().imageAssets).toEqual([asset])
})

it('loads the replacement service without accepting an old service response', async () => {
  let resolve!: (value: unknown) => void
  api.list.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  render(<ImageAssetsPanel />)
  const nextAsset = { ...asset, id: 'next', name: 'next.png', originalName: 'next.png' }
  api.list.mockResolvedValue({ success: true, data: [nextAsset] })
  let restoreNext = () => {}
  act(() => { restoreNext = configureStudioConnection('http://next.fixture', async () => Response.json({})) })
  try {
    await screen.findByText('next.png', { exact: true })
    await act(async () => resolve({ success: true, data: [asset] }))
    expect(useWorkflowStore.getState().imageAssets).toEqual([nextAsset])
  } finally { cleanup(); restoreNext() }
})

it('applies the shared metadata default for an omitted path', async () => {
  const withoutPath: Partial<typeof asset> = { ...asset }
  delete withoutPath.path
  api.list.mockResolvedValue({ success: true, data: [withoutPath] })
  render(<ImageAssetsPanel />)
  await waitFor(() => expect(screen.queryByText('正在加载图像资源…')).toBeNull())
  expect(useWorkflowStore.getState().imageAssets[0].path).toBeNull()
})

it('does not present loading or failed reads as an empty resource directory', async () => {
  let resolve!: (value: unknown) => void
  useWorkflowStore.setState({ imageAssets: [] })
  api.list.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  render(<ImageAssetsPanel />)
  expect(screen.queryByText('暂无图像文件')).toBeNull()
  await act(async () => resolve({ success: false, error: '不可用' }))
  expect(screen.getByRole('alert')).toBeTruthy()
  expect(screen.queryByText('暂无图像文件')).toBeNull()
  api.list.mockResolvedValue({ success: true, data: [] })
  fireEvent.click(screen.getByRole('button', { name: '重试加载图像资源' }))
  await screen.findByText('暂无图像文件')
})

it('still loads folders when another cache consumer refreshed images in the meantime', async () => {
  let resolve!: (value: unknown) => void
  api.listFolders.mockResolvedValue({ success: true, data: ['资料'] })
  api.list.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  render(<ImageAssetsPanel />)
  act(() => useWorkflowStore.getState().setImageAssets([{ ...asset }]))
  await act(async () => resolve({ success: true, data: [asset] }))
  expect(screen.getByText('资料', { exact: true })).toBeTruthy()
})
