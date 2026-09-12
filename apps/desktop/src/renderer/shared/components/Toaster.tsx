import { useLayoutEffect, useState } from 'react'
import { Button } from './ui/button'

export type Toast = { id: number; title: string; tone?: 'success' | 'error' | 'info' }
type NotifyInput = Omit<Toast, 'id'>
let nextId = 1
const listeners = new Set<(toast: Toast) => void>()
const pending: Toast[] = []
export function notify(input: NotifyInput) { const toast = { ...input, id: nextId++ }; if (listeners.size === 0) pending.push(toast); else listeners.forEach((listener) => listener(toast)); return toast.id }

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>(() => pending.splice(0))
  const [exiting, setExiting] = useState<Set<number>>(() => new Set())
  useLayoutEffect(() => {
    const beginExit = (toast: Toast) => { setExiting((current) => new Set(current).add(toast.id)); window.setTimeout(() => setToasts((current) => current.filter((item) => item.id !== toast.id)), 150) }
    const schedule = (toast: Toast) => window.setTimeout(() => beginExit(toast), 2600)
    const listener = (toast: Toast) => { setToasts((current) => [...current, toast]); schedule(toast) }
    listeners.add(listener)
    toasts.forEach(schedule)
    return () => { listeners.delete(listener) }
  }, [])
  return <div className="pointer-events-none fixed bottom-4 right-4 z-[100] grid w-[min(24rem,calc(100vw-2rem))] gap-2" aria-live="polite">{toasts.map((toast) => <div key={toast.id} className={`${exiting.has(toast.id) ? 'toast-exit' : 'toast-enter'} pointer-events-auto flex items-center justify-between gap-4 rounded-control border border-line bg-surface px-4 py-3 text-sm text-ink shadow-lg`} role="status" data-tone={toast.tone}><span className="min-w-0 break-words">{toast.title}</span><Button variant="ghost" className="h-7 shrink-0 px-2 text-xs" aria-label="关闭通知" onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))}>关闭</Button></div>)}</div>
}
