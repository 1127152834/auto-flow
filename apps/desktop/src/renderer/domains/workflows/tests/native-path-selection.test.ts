import { afterEach, expect, it, vi } from 'vitest'
import { nativePathSelection } from '../lib/nativePathSelection'
afterEach(() => vi.unstubAllGlobals())
it('uses the registered desktop picker and preserves selection cancellation', async () => {
  const chooseWorkflowPath = vi.fn().mockResolvedValueOnce({ ok: true, value: { value: '/tmp/selected.txt' } }).mockResolvedValueOnce({ ok: true, value: {} }).mockResolvedValueOnce({ ok: false, error: { code: 'WORKSPACE_CHANGED', message: '工作区已变化' } })
  vi.stubGlobal('autoflow', { chooseWorkflowPath })
  expect(await nativePathSelection({ kind: 'file', title: '输入文件' })).toMatchObject({ success: true, data: { path: '/tmp/selected.txt' } })
  expect(chooseWorkflowPath).toHaveBeenCalledWith({ kind: 'file', title: '输入文件' })
  expect(await nativePathSelection({ kind: 'folder' })).toMatchObject({ success: true, data: { path: null } })
  expect(await nativePathSelection({ kind: 'file' })).toEqual({ success: false, error: '工作区已变化', data: undefined })
})
