import { afterEach, expect, it, vi } from 'vitest'
const fixture = vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
  return { handlers: new Map<string, (value: unknown) => void>(), emit: vi.fn() }
})
vi.mock('../api/event-client', () => ({ StudioEventClient: class {
  connected = true
  on(event: string, handler: (value: unknown) => void) { fixture.handlers.set(event, handler) }
  off(event: string) { fixture.handlers.delete(event) }
  removeAllListeners() { fixture.handlers.clear() }
  disconnect() {}
  emit = fixture.emit
} }))
import { socketService } from '../events'
afterEach(() => { socketService.disconnect(); vi.restoreAllMocks(); fixture.emit.mockClear() })
it.each(['play_music', 'play_video', 'view_image'])('rejects obsolete %s events with a failure acknowledgment', action => {
  socketService.connect()
  fixture.handlers.get(`execution:${action}`)?.({ requestId: 'obsolete-1', audioUrl: '/secret', videoUrl: '/secret', imageUrl: '/secret' })
  expect(fixture.emit).toHaveBeenCalledWith(`${action}_result`, { requestId: 'obsolete-1', success: false, error: '该媒体节点已排除，不支持执行' })
})
it('still cancels retained speech notifications when stopping', () => {
  const cancel = vi.fn()
  vi.stubGlobal('speechSynthesis', { cancel })
  socketService.connect()
  socketService.stopExecution('current')
  expect(cancel).toHaveBeenCalledOnce()
  expect(fixture.emit).toHaveBeenCalledWith('execution_stop', { workflowId: 'current' })
  vi.unstubAllGlobals()
})
