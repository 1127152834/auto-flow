import { describe, expect, it, vi } from 'vitest'
import type { ProjectFileBridge } from '../../../shared/project-files'
import type { StreamingApiClient } from '../../shared/api/client'
import { createProjectFileClient } from './project-file-client'
const bridge = (): ProjectFileBridge => ({
  chooseExcelInput: vi.fn(async () => ({ ok: true as const, value: null })),
  chooseXlsxOutput: vi.fn(async () => ({ ok: true as const, value: null })),
  getProjectFileContext: vi.fn(async () => ({ ok: true as const, value: { windowId: 7, windowToken: 'test-window-proof' } })),
})
describe('project file window authority', () => {
  it('returns cancellation without issuing HTTP', async () => {
    const request = vi.fn()
    const files = createProjectFileClient({ request } as unknown as StreamingApiClient, bridge(), 'p', () => true)
    expect(await files.chooseInput()).toBeNull()
    expect(await files.chooseOutput('资料.xlsx')).toBeNull()
    expect(request).not.toHaveBeenCalled()
  })
  it('attaches current window proof without accepting renderer filesystem paths', async () => {
    const request = vi.fn(async () => ({ inspected: true }))
    const files = createProjectFileClient({ request } as unknown as StreamingApiClient, bridge(), 'p', () => true)
    await files.request('/inspect', { method: 'POST', headers: { 'Idempotency-Key': 'key' }, body: { selectionToken: 'selected' } })
    expect(request).toHaveBeenCalledWith('/inspect', expect.objectContaining({ headers: {
      'idempotency-key': 'key', 'x-autoflow-file-window-id': '7', 'x-autoflow-file-window-token': 'test-window-proof',
    } }))
    expect(JSON.stringify(request.mock.calls)).not.toContain('path')
  })
  it('revokes a late window context before HTTP submission', async () => {
    let current = true
    const desktop = bridge()
    desktop.getProjectFileContext = async () => { current = false; return { ok: true as const, value: { windowId: 7, windowToken: 'test' } } }
    const request = vi.fn()
    const files = createProjectFileClient({ request } as unknown as StreamingApiClient, desktop, 'p', () => current)
    await expect(files.request('/inspect')).rejects.toThrow('上下文已切换')
    expect(request).not.toHaveBeenCalled()
  })
  it('requires a fresh file choice when the authority is absent', async () => {
    const desktop = bridge(); desktop.getProjectFileContext = async () => ({ ok: true as const, value: null })
    const request = vi.fn()
    await expect(createProjectFileClient({ request } as unknown as StreamingApiClient, desktop, 'p', () => true).request('/inspect')).rejects.toThrow('重新选择')
    expect(request).not.toHaveBeenCalled()
  })
  it('preserves bridge error classification and code for safe presentation mapping', async () => {
    const desktop=bridge();desktop.chooseExcelInput=vi.fn(async()=>({ok:false as const,error:{code:'EXTERNAL_LINK_FAILED',message:'internal detail'}}))
    const files=createProjectFileClient({request:vi.fn()} as unknown as StreamingApiClient,desktop,'p',()=>true)
    await expect(files.chooseInput()).rejects.toMatchObject({name:'Error',code:'EXTERNAL_LINK_FAILED',message:'internal detail'})
  })
})
