import { useLayoutEffect, useState } from 'react'
import { IconButton } from './ui/icon-button'
import { X } from '@phosphor-icons/react'

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
    const timers = new Set<number>()
    const later = (callback: () => void, delay: number) => { const id = window.setTimeout(() => { timers.delete(id); callback() }, delay); timers.add(id); return id }
    const beginExit = (toast: Toast) => { setExiting((current) => new Set(current).add(toast.id)); later(() => setToasts((current) => current.filter((item) => item.id !== toast.id)), 150) }
    const schedule = (toast: Toast) => later(() => beginExit(toast), 2600)
    const listener = (toast: Toast) => { setToasts((current) => [...current, toast]); schedule(toast) }
    listeners.add(listener)
    toasts.forEach(schedule)
    return () => { listeners.delete(listener); timers.forEach(window.clearTimeout) }
  }, [])
  return <div className="pointer-events-none fixed bottom-4 right-4 z-[var(--layer-toast)] grid w-[min(24rem,calc(100vw-2rem))] gap-2" aria-live="polite">{toasts.map((toast) => <div key={toast.id} className={`${exiting.has(toast.id) ? 'toast-exit' : 'toast-enter'} pointer-events-auto flex items-center justify-between gap-4 rounded-control border border-line bg-surface px-4 py-3 text-sm text-ink shadow-lg`} role="status" data-tone={toast.tone ?? 'info'}><span>{toast.title}</span><IconButton variant="ghost" size="sm" aria-label="关闭通知" onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))}><X size={16} aria-hidden /></IconButton></div>)}</div>
}
