import type { JsScriptOutcome } from './jsScript'
/** A dedicated worker keeps synchronous scripts cancellable and away from the Studio DOM. */
export function runJsScript(code: string, variables: Record<string, unknown>, signal: AbortSignal): Promise<JsScriptOutcome> {
  if (signal.aborted) return Promise.reject(new DOMException('脚本已取消', 'AbortError'))
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./js-script.worker.ts', import.meta.url), { type: 'module' })
    const cleanup = () => { clearTimeout(timer); signal.removeEventListener('abort', cancel); worker.terminate() }
    const cancel = () => { cleanup(); reject(new DOMException('脚本已取消', 'AbortError')) }
    const timer = setTimeout(() => { cleanup(); resolve({ success: false, error: '脚本执行超过 30 秒，已终止' }) }, 30000)
    signal.addEventListener('abort', cancel, { once: true })
    worker.onmessage = (event: MessageEvent<JsScriptOutcome>) => { cleanup(); resolve(event.data) }
    worker.onerror = (event) => { event.preventDefault(); cleanup(); resolve({ success: false, error: event.message || '脚本 Worker 执行失败' }) }
    try { worker.postMessage({ code, variables }) } catch (error) { cleanup(); reject(error) }
  })
}
