import { evaluateJsScript } from './jsScript'
self.onmessage = (event: MessageEvent<{ code: string; variables: Record<string, unknown> }>) => {
  self.postMessage(evaluateJsScript(event.data.code, event.data.variables))
}
