import { CheckCircle, Info, WarningCircle } from '@phosphor-icons/react'
import { useLayoutEffect, useRef, useState } from 'react'
import { Button } from './ui/button'

export type Toast = { id: number; title: string; tone?: 'success' | 'error' | 'info'; operationId?: string }
type Notice = Toast & { summaryCount?: number }
type NotifyInput = Omit<Toast, 'id'>
let nextId = 1
const listeners = new Set<(toast: Notice) => void>()
const identities = new Map<string, number>()
let pending: Notice[] = []
const forget = (toast: Notice) => { if (toast.operationId && identities.get(toast.operationId) === toast.id) identities.delete(toast.operationId) }

function bounded(current: Notice[], toast: Notice): Notice[] {
  if (current.some(item => item.id === toast.id)) return current.map(item => item.id === toast.id ? toast : item)
  if (current.length < 3) return [...current, toast]
  // Only ordinary success notices may be summarized; failures remain explicit.
  let index = -1
  current.forEach((item, position) => { if (item.summaryCount || item.tone === 'success' && !item.operationId) index = position })
  if (toast.tone === 'success' && !toast.operationId && index >= 0) {
    const old = current[index]!, count = (old.summaryCount ?? 1) + 1
    return current.map((item, position) => position === index ? { id: old.id, title: `另有 ${count} 项操作已完成`, tone: 'success', summaryCount: count } : item)
  }
  forget(current[0]!)
  return [...current.slice(1), toast]
}

export function notify(input: NotifyInput) {
  const id = input.operationId ? identities.get(input.operationId) ?? nextId++ : nextId++
  if (input.operationId) identities.set(input.operationId, id)
  const toast = { ...input, id }
  if (listeners.size === 0) pending = bounded(pending, toast)
  else listeners.forEach(listener => listener(toast))
  return id
}

export function Toaster() {
  // Reading without consuming also works with Strict Mode's repeated initial render.
  const [toasts, setToasts] = useState<Notice[]>(() => [...pending])
  const latest = useRef(toasts)
  const [exiting, setExiting] = useState<Set<number>>(() => new Set())
  const dismissRef = useRef<(id: number) => void>(() => {})
  useLayoutEffect(() => {
    pending = []
    const timers = new Map<number, { dismiss?: number; remove?: number }>()
    const clear = (id: number) => { const timer = timers.get(id); if (timer) { window.clearTimeout(timer.dismiss); window.clearTimeout(timer.remove); timers.delete(id) } }
    const remove = (id: number) => {
      clear(id)
      const previous = latest.current.find(item => item.id === id)
      if (previous) forget(previous)
      latest.current = latest.current.filter(item => item.id !== id)
      setToasts(latest.current)
      setExiting(current => { const next = new Set(current); next.delete(id); return next })
    }
    const schedule = (toast: Notice) => {
      clear(toast.id)
      setExiting(current => { const next = new Set(current); next.delete(toast.id); return next })
      timers.set(toast.id, { dismiss: window.setTimeout(() => {
        setExiting(current => new Set(current).add(toast.id))
        timers.set(toast.id, { remove: window.setTimeout(() => remove(toast.id), 150) })
      }, 2600) })
    }
    const listener = (toast: Notice) => {
      const previous = latest.current, next = bounded(previous, toast)
      for (const old of previous) if (!next.some(item => item.id === old.id)) clear(old.id)
      latest.current = next; setToasts(next)
      for (const item of next) if (previous.find(old => old.id === item.id) !== item) schedule(item)
    }
    dismissRef.current = remove
    listeners.add(listener)
    latest.current.forEach(toast => { if (toast.operationId) identities.set(toast.operationId, toast.id); schedule(toast) })
    return () => {
      listeners.delete(listener)
      timers.forEach((_, id) => clear(id))
      latest.current.forEach(forget)
    }
  }, [])
  return <div className="pointer-events-none fixed top-24 right-4 z-[100] grid w-[min(24rem,calc(100vw-2rem))] gap-2" aria-live="polite">{toasts.map(toast => <div key={toast.id} className={`${exiting.has(toast.id) ? 'toast-exit' : 'toast-enter'} pointer-events-auto flex items-center justify-between gap-4 rounded-control border border-line bg-surface px-4 py-3 text-sm text-ink shadow-lg`} role="status" data-tone={toast.tone}><span className="flex min-w-0 items-start gap-2">{toast.tone === 'success' ? <CheckCircle aria-hidden size={20} className="shrink-0 text-success" /> : toast.tone === 'error' ? <WarningCircle aria-hidden size={20} className="shrink-0 text-danger" /> : <Info aria-hidden size={20} className="shrink-0 text-muted" />}<span className="min-w-0 break-words">{toast.title}</span></span><Button variant="ghost" className="h-7 shrink-0 px-2 text-xs" aria-label="关闭通知" onClick={() => dismissRef.current(toast.id)}>关闭</Button></div>)}</div>
}
