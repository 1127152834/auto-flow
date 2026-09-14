import type { components } from '../../../shared/api/generated'
type SpeechRequest = components['schemas']['StudioSpeechRequest']
type SpeechOutcome = Pick<components['schemas']['StudioSpeechResult'], 'success' | 'error'>

export function isSpeechRequest(value: unknown): value is SpeechRequest {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const data = value as Record<string, unknown>
  return ['requestId','workflowId','nodeId','text','lang'].every(key => typeof data[key] === 'string' && data[key].trim())
    && ['rate','pitch'].every(key => typeof data[key] === 'number' && Number.isFinite(data[key]) && data[key] >= 0.5 && data[key] <= 2)
    && typeof data.volume === 'number' && Number.isFinite(data.volume) && data.volume >= 0 && data.volume <= 1
}

export function runSpeech(request: SpeechRequest, signal: AbortSignal): Promise<SpeechOutcome> {
  if (signal.aborted) return Promise.reject(new DOMException('朗读已取消','AbortError'))
  if (!isSpeechRequest(request)) return Promise.resolve({success:false,error:'语音请求参数无效'})
  const engine = window.speechSynthesis
  if (!engine || typeof SpeechSynthesisUtterance === 'undefined') return Promise.resolve({success:false,error:'当前环境不支持语音合成'})
  return new Promise((resolve,reject) => {
    let utterance: SpeechSynthesisUtterance | undefined
    let settled = false
    const finish = (outcome: SpeechOutcome | null, cancel = false) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal.removeEventListener('abort',abort)
      if (utterance) { utterance.onend = null; utterance.onerror = null }
      if (cancel) engine.cancel()
      if (outcome) resolve(outcome)
      else reject(new DOMException('朗读已取消','AbortError'))
    }
    const abort = () => finish(null,true)
    const timer = setTimeout(() => finish({success:false,error:'朗读超过60秒，已取消'},true),60000)
    signal.addEventListener('abort',abort,{once:true})
    try {
      utterance = new SpeechSynthesisUtterance(request.text)
      utterance.lang = request.lang; utterance.rate = request.rate; utterance.pitch = request.pitch; utterance.volume = request.volume
      utterance.onend = () => finish({success:true,error:null})
      utterance.onerror = event => finish({success:false,error:`语音合成失败: ${event.error}`})
      engine.speak(utterance)
    } catch (error) {
      finish({success:false,error:error instanceof Error ? error.message : String(error)})
    }
  })
}
