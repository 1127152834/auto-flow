import { useEffect, useState } from 'react'
import { elementPickerApi } from '../api'

export type SelectorMatchState =
  | { status: 'idle' | 'checking' | 'disabled' | 'noBrowser' }
  | { status: 'ok'; count: number }
  | { status: 'error'; error: string }

export const SELECTOR_MATCH_DEBOUNCE_MS = 500
const NO_BROWSER = /浏览器未(打开|连接|启动)/

/** 选择器匹配数：防抖、单飞（新请求作废旧结果）、运行中暂停、不自动启动浏览器。 */
export function useSelectorMatchCount(selector: string, hints: Record<string, unknown> | undefined, enabled: boolean): SelectorMatchState {
  const [state, setState] = useState<SelectorMatchState>({ status: 'idle' })
  const hintsKey = JSON.stringify(hints ?? null)

  useEffect(() => {
    if (!enabled) { setState({ status: 'disabled' }); return }
    if (!selector.trim()) { setState({ status: 'idle' }); return }
    let current = true
    setState({ status: 'checking' })
    const timer = setTimeout(async () => {
      let next: SelectorMatchState
      try {
        const res = await elementPickerApi.testSelector(selector, hints, false)
        const message = res.error || res.data?.error || '定位测试失败，请检查选择器'
        if (!res.success || !res.data?.success) next = NO_BROWSER.test(message) ? { status: 'noBrowser' } : { status: 'error', error: message }
        else next = { status: 'ok', count: res.data.count }
      } catch (e) {
        next = { status: 'error', error: e instanceof Error ? e.message : String(e) }
      }
      if (current) setState(next)
    }, SELECTOR_MATCH_DEBOUNCE_MS)
    return () => { current = false; clearTimeout(timer) }
    // hints 以序列化值比较，避免调用方每次渲染新建对象导致重复请求
  }, [selector, hintsKey, enabled])

  return state
}
