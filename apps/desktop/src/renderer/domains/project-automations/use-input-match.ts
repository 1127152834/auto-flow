import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { safeProjectError } from '../projects/presentation-error'
import type { InputMatchFetcher, InputMatchItem } from './input-match-api'
import type { AutomationWrite } from './types'

const generic = safeProjectError(null)
/** Known codes get their business wording; anything else keeps the original reason (AGENTS rule 2). */
export function describeMatchError(error: unknown) {
  const known = safeProjectError(error)
  return known !== generic ? known : error instanceof Error && error.message ? error.message : known
}

const validationCodes = new Set(['VALIDATION_ERROR', 'INVALID_PROJECT_DATA', 'INVALID_PROJECT_DATA_QUERY'])
export const isValidationFailure = (error: unknown) => Boolean(error && typeof error === 'object' && (('code' in error && typeof error.code === 'string' && validationCodes.has(error.code)) || ('status' in error && error.status === 422)))

export type InputMatchState = { status: 'idle' | 'loading' | 'ready' | 'error'; items: Map<string, InputMatchItem>; error: string | null; /** A validation-class answer (the draft is just not complete yet): shown as a quiet hint, not a warning. */ quiet: boolean; retry(): void }

/** Debounced, single-flight pre-check of the draft input plan; the previous answer stays visible while a new one loads. */
export function useInputMatch({ fetcher, plan, delayMs = 600 }: { fetcher: InputMatchFetcher | undefined; plan: AutomationWrite['inputPlan']; delayMs?: number }): InputMatchState {
  const [items, setItems] = useState<Map<string, InputMatchItem>>(() => new Map())
  const [status, setStatus] = useState<InputMatchState['status']>('idle')
  const [error, setError] = useState<string | null>(null)
  const [quiet, setQuiet] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const latest = useRef(fetcher); latest.current = fetcher
  const immediate = useRef(false)
  const active = Boolean(fetcher) && plan.inputs.length > 0
  const key = useMemo(() => JSON.stringify(plan), [plan])
  useEffect(() => {
    if (!active) { setStatus('idle'); setError(null); return }
    const controller = new AbortController()
    setStatus('loading')
    const wait = immediate.current ? 0 : delayMs
    immediate.current = false
    const timer = setTimeout(() => {
      latest.current!(JSON.parse(key), controller.signal).then(result => {
        if (controller.signal.aborted) return
        setItems(new Map(result.inputs.map(item => [item.inputId, item]))); setError(null); setStatus('ready')
      }, reason => {
        if (controller.signal.aborted) return
        setError(describeMatchError(reason)); setQuiet(isValidationFailure(reason)); setStatus('error')
      })
    }, wait)
    return () => { clearTimeout(timer); controller.abort() }
  }, [active, key, delayMs, attempt])
  const retry = useCallback(() => { immediate.current = true; setAttempt(value => value + 1) }, [])
  return { status, items, error, quiet, retry }
}
