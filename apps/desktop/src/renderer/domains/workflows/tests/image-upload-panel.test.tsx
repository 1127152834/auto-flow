import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ImageAssetsPanel } from '../components/ImageAssetsPanel'
import { useWorkflowStore } from '../editor-store'
import { configureStudioConnection } from '../api/config'
import { mockRequest } from '../api/mock-server'
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('adds an uploaded image to the visible resource list using the source upload envelope', async () => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
  useWorkflowStore.setState({ imageAssets: [] })
  const restore = configureStudioConnection('http://autoflow-studio.mock', mockRequest)
  const view = render(<ImageAssetsPanel />)
  try {
    await waitFor(() => expect(screen.getByText(/暂无图像文件/)).toBeTruthy())
    const file = new File([new Uint8Array([137, 80, 78, 71])], '上传验收.png', { type: 'image/png' })
    fireEvent.change(view.container.querySelector('input[type="file"]')!, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByAltText('上传验收.png')).toBeTruthy())
    expect(useWorkflowStore.getState().imageAssets).toMatchObject([{ originalName: '上传验收.png', size: 4, folder: '' }])
    expect(screen.queryByText(/成功 0 个/)).toBeNull()
  } finally { view.unmount(); restore(); localStorage.removeItem('autoflow:studio:mock:image-assets') }
})
