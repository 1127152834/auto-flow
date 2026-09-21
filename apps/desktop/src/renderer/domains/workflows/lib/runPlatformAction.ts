import type { components } from '../../../shared/api/generated'
import type { StudioPlatformAction } from '../../../../shared/studio-platform'

type Request = components['schemas']['StudioDesktopActionRequest']
type Outcome = Pick<components['schemas']['StudioDesktopActionResult'], 'success' | 'value' | 'error'>

export function isPlatformActionRequest(value: unknown): value is Request {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const request = value as Record<string, unknown>
  return typeof request.requestId === 'string' && !!request.requestId.trim()
    && typeof request.workflowId === 'string' && !!request.workflowId.trim()
    && typeof request.nodeId === 'string' && !!request.nodeId.trim()
    && ['clipboard_write_text', 'clipboard_write_image', 'clipboard_read_text', 'beep', 'notification', 'open_path'].includes(String(request.action))
    && !!request.payload && typeof request.payload === 'object' && !Array.isArray(request.payload)
}

function actionFrom(request: Request): StudioPlatformAction | null {
  const payload = request.payload
  if (request.action === 'clipboard_write_text' && typeof payload.text === 'string') return { action: request.action, text: payload.text }
  if (request.action === 'clipboard_write_image' && typeof payload.path === 'string') return { action: request.action, path: payload.path }
  if (request.action === 'clipboard_read_text') return { action: request.action }
  if (request.action === 'beep' && Number.isSafeInteger(payload.count) && typeof payload.interval === 'number') {
    return { action: request.action, count: Number(payload.count), interval: payload.interval }
  }
  if (request.action === 'notification' && typeof payload.title === 'string' && typeof payload.message === 'string'
    && typeof payload.duration === 'number' && typeof payload.playSound === 'boolean') {
    return { action: request.action, title: payload.title, message: payload.message, duration: payload.duration, playSound: payload.playSound }
  }
  if (request.action === 'open_path' && typeof payload.path === 'string') return { action: request.action, path: payload.path }
  return null
}

export async function runPlatformAction(request: Request, signal: AbortSignal): Promise<Outcome> {
  if (signal.aborted) throw new DOMException('平台操作已取消', 'AbortError')
  if (!isPlatformActionRequest(request)) return { success: false, value: null, error: '平台操作请求参数无效' }
  const action = actionFrom(request)
  const bridge = window.autoflow?.runStudioPlatformAction
  if (!action || !bridge) return { success: false, value: null, error: '当前环境不支持平台操作' }
  if (action.action === 'beep') {
    for (let index = 0; index < action.count; index++) {
      if (signal.aborted) throw new DOMException('平台操作已取消', 'AbortError')
      const result = await bridge({ action: 'beep', count: 1, interval: 0 })
      if (!result.ok) return { success: false, value: null, error: result.error.message }
      if (index + 1 < action.count && action.interval > 0) await wait(action.interval * 1000, signal)
    }
    return { success: true, value: null, error: null }
  }
  const result = await bridge(action)
  if (signal.aborted) throw new DOMException('平台操作已取消', 'AbortError')
  return result.ok
    ? { success: true, value: result.value.value ?? null, error: null }
    : { success: false, value: null, error: result.error.message }
}

function wait(milliseconds: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException('平台操作已取消', 'AbortError')) }
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, milliseconds)
    signal.addEventListener('abort', abort, { once: true })
    if (signal.aborted) abort()
  })
}
