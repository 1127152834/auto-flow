import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it } from 'vitest'
import { ImageAssetsPanel } from '../components/ImageAssetsPanel'
import { useWorkflowStore } from '../editor-store'
import { configureStudioConnection } from '../api/config'
const asset = { id: 'image', name: 'image.png', originalName: 'image.png', size: 1, uploadedAt: '', folder: '', extension: 'png', path: null }
let restore = () => {}
beforeEach(() => {
  useWorkflowStore.setState({ imageAssets: [asset] })
  restore = configureStudioConnection('http://images.fixture', async (input, init) => {
    if (init?.method === 'DELETE' || init?.method === 'PUT') return Response.json({})
    return Response.json(String(input).endsWith('/image-assets') ? [asset] : [])
  })
})
afterEach(() => { cleanup(); restore() })
it('shows an unconfirmed delete and retains the image', async () => {
  render(<ImageAssetsPanel />)
  await waitFor(() => expect(screen.queryByText('正在加载图像资源…')).toBeNull())
  fireEvent.contextMenu(screen.getByText('image.png', { exact: true }))
  fireEvent.click(screen.getByRole('button', { name: '删除' }))
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  await screen.findByText(/图像资源操作未返回有效确认/)
  expect(useWorkflowStore.getState().imageAssets).toEqual([asset])
})
it('keeps the requested rename editable after an unconfirmed response', async () => {
  render(<ImageAssetsPanel />)
  await waitFor(() => expect(screen.queryByText('正在加载图像资源…')).toBeNull())
  fireEvent.contextMenu(screen.getByText('image.png', { exact: true }))
  fireEvent.click(screen.getByRole('button', { name: '重命名' }))
  const input = screen.getByDisplayValue('image.png')
  fireEvent.change(input, { target: { value: 'retry.png' } })
  fireEvent.blur(input)
  await screen.findByText(/图像资源操作未返回有效确认/)
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  await waitFor(() => expect(screen.getByDisplayValue('retry.png')).toBeTruthy())
  expect(useWorkflowStore.getState().imageAssets).toEqual([asset])
})

it.each(['asset', 'folder'])('submits %s rename once when Enter and blur overlap and preserves retry after failure', async kind => {
  const originalName = kind === 'asset' ? 'image.png' : '资料'
  const requestedName = kind === 'asset' ? 'retry.png' : '新资料'
  let writes = 0
  let resolve!: (value: Response) => void
  const restorePending = configureStudioConnection('http://images.fixture', async (input, init) => {
    if (init?.method === 'PUT') { writes++; return new Promise(done => { resolve = done }) }
    return Response.json(String(input).endsWith('/image-assets') ? [asset] : String(input).endsWith('/folders') ? ['资料'] : [])
  })
  try {
    render(<ImageAssetsPanel />)
    await waitFor(() => expect(screen.queryByText('正在加载图像资源…')).toBeNull())
    fireEvent.contextMenu(screen.getByText(originalName, { exact: true }))
    fireEvent.click(screen.getByRole('button', { name: '重命名' }))
    const input = screen.getByDisplayValue(originalName) as HTMLInputElement
    fireEvent.change(input, { target: { value: requestedName } })
    fireEvent.keyDown(input, { key: 'Enter' })
    fireEvent.blur(input)
    expect(writes).toBe(1)
    expect(input.disabled).toBe(true)
    await act(async () => resolve(Response.json({ success: false, error: '请重试' })))
    await screen.findByText('请重试')
    fireEvent.click(screen.getByRole('button', { name: '确定' }))
    await waitFor(() => expect((screen.getByDisplayValue(requestedName) as HTMLInputElement).disabled).toBe(false))
  } finally { cleanup(); restorePending() }
})
