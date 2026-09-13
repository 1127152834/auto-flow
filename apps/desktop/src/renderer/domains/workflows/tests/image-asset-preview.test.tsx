import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ImageAssetPreview } from '../components/controls/image-asset-preview'
import { configureStudioConnection } from '../api/config'
const asset = { id: 'asset/a', path: '/workspace/a.png', originalName: '受控图片' }
let restore: () => void
const request = vi.fn()
const createUrl = vi.fn(() => 'blob:controlled')
const revokeUrl = vi.fn()
beforeEach(() => {
  restore = configureStudioConnection('http://autoflow-studio.mock', request)
  vi.spyOn(URL, 'createObjectURL').mockImplementation(createUrl)
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(revokeUrl)
  request.mockReset(); createUrl.mockClear(); revokeUrl.mockClear()
})
afterEach(() => { cleanup(); restore(); vi.restoreAllMocks() })
const image = () => new Response(new Uint8Array([137, 80, 78, 71]), { headers: { 'Content-Type': 'image/png' } })

it.each(['thumbnail', 'file'] as const)('loads %s using the transport and releases its URL on unmount', async variant => {
  request.mockResolvedValue(image())
  const view = render(<ImageAssetPreview asset={asset} variant={variant} />)
  expect(screen.getByRole('status')).toHaveTextContent('加载中')
  await waitFor(() => expect(screen.getByAltText('受控图片')).toHaveAttribute('src', 'blob:controlled'))
  expect(request.mock.calls[0][0]).toBe(`http://autoflow-studio.mock/api/image-assets/asset%2Fa/${variant}`)
  const signal = request.mock.calls[0][1].signal
  view.unmount()
  expect(signal.aborted).toBe(true); expect(revokeUrl).toHaveBeenCalledWith('blob:controlled')
})

it('does not create a URL or replace a new asset with late bytes', async () => {
  let resolve!: (response: Response) => void
  request.mockImplementationOnce(() => new Promise<Response>(done => { resolve = done })).mockResolvedValue(image())
  const view = render(<ImageAssetPreview asset={asset} />)
  const oldSignal = request.mock.calls[0][1].signal
  view.rerender(<ImageAssetPreview asset={{ ...asset, id: 'b', originalName: '新图片' }} />)
  await waitFor(() => expect(screen.getByAltText('新图片')).toHaveAttribute('src', 'blob:controlled'))
  resolve(image())
  await waitFor(() => expect(oldSignal.aborted).toBe(true))
  expect(createUrl).toHaveBeenCalledOnce(); expect(screen.queryByAltText('受控图片')).not.toBeInTheDocument()
})

it.each([404, 403, 500])('shows an explicit retry after HTTP %i without leaking the service URL to img', async status => {
  request.mockResolvedValueOnce(Response.json({ error: '失败' }, { status })).mockResolvedValue(image())
  render(<ImageAssetPreview asset={asset} />)
  const retry = await screen.findByRole('button', { name: '重新加载图片：受控图片' })
  expect(retry).toHaveAttribute('title', `图片读取失败（${status}）`)
  expect(screen.queryByAltText('受控图片')).not.toBeInTheDocument()
  fireEvent.click(retry)
  await screen.findByAltText('受控图片'); expect(request).toHaveBeenCalledTimes(2)
})

it('rejects a JSON success payload as image bytes', async () => {
  request.mockResolvedValue(Response.json({ success: true }))
  render(<ImageAssetPreview asset={asset} />)
  expect(await screen.findByRole('button', { name: '重新加载图片：受控图片' })).toHaveAttribute('title', '服务返回的内容不是图片')
  expect(createUrl).not.toHaveBeenCalled()
})

it('keeps existing inline images local and reports decode errors', () => {
  render(<ImageAssetPreview asset={{ ...asset, path: 'data:image/png;base64,aGVsbG8=' }} />)
  const img = screen.getByAltText('受控图片')
  expect(request).not.toHaveBeenCalled()
  fireEvent.error(img)
  expect(screen.getByRole('button', { name: '重新加载图片：受控图片' })).toHaveAttribute('title', '图片无法解码')
})

it('cancels an unfinished read when removed', async () => {
  request.mockImplementation((_url, init) => new Promise((_resolve, reject) => init.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))))
  const view = render(<ImageAssetPreview asset={asset} />)
  view.unmount()
  await waitFor(() => expect(request.mock.calls[0][1].signal.aborted).toBe(true))
  expect(createUrl).not.toHaveBeenCalled()
})
