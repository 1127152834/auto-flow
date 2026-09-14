import { expect, it, vi } from 'vitest'
import { apiRequest, recorderApi } from '../api'
import { configureStudioConnection } from '../api/config'

it.each(['start', 'stop', 'save', 'read'] as const)('binds %s to the connection selected when the request is called', async operation => {
  const oldService = vi.fn(async () => Response.json({ success: true, source: 'old' }))
  const nextService = vi.fn(async () => Response.json({ success: true, source: 'next' }))
  const restore = configureStudioConnection('http://original.fixture', oldService)
  let restoreNext = () => {}
  try {
    const pending = operation === 'start' ? recorderApi.start('owned-session')
      : operation === 'stop' ? recorderApi.stop('owned-session', 4)
      : apiRequest('/webdav/config', operation === 'save' ? { method: 'POST', body: JSON.stringify({ remoteDir: 'original-workspace' }) } : {})
    restoreNext = configureStudioConnection('http://replacement.fixture', nextService)
    const result = await pending
    expect(oldService).toHaveBeenCalledOnce()
    expect(nextService).not.toHaveBeenCalled()
    if(operation==='start'||operation==='stop')expect(result).toMatchObject({success:false,error:'录制所属服务连接已变更，响应未应用'})
    else expect(result.data).toMatchObject({ source: 'old' })
    expect(String((oldService.mock.calls as unknown[][])[0][0])).toMatch(/^http:\/\/original\.fixture\/api\//)
    await apiRequest('/webdav/config')
    expect(nextService).toHaveBeenCalledOnce()
  } finally { restoreNext(); restore() }
})
