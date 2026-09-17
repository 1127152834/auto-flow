import type { ReactNode } from 'react'
import type { Capability, HealthSnapshot } from '../api'

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString()
}

export function StatusPill({ tone = 'neutral', children }: {
  tone?: 'success' | 'warning' | 'danger' | 'neutral'
  children: ReactNode
}) {
  const colors = {
    success: 'bg-sage-soft text-sage-strong',
    warning: 'bg-amber-50 text-amber-800',
    danger: 'bg-red-50 text-red-700',
    neutral: 'bg-surface-subtle text-muted',
  }
  return <span className={`inline-flex w-fit shrink-0 items-center whitespace-nowrap gap-1 rounded-control px-2.5 py-1 text-xs font-semibold ${colors[tone]}`}>{children}</span>
}

export function HealthPill({ health }: { health: HealthSnapshot }) {
  const values: Record<HealthSnapshot['state'], { label: string; tone: 'success' | 'danger' | 'neutral' }> = {
    healthy: { label: '健康', tone: 'success' },
    unhealthy: { label: '异常', tone: 'danger' },
    checking: { label: '检测中', tone: 'neutral' },
    untested: { label: '未检测', tone: 'neutral' },
  }
  const value = values[health.state]
  return <StatusPill tone={value.tone}>{value.label}</StatusPill>
}

export function CapabilityNotice({ capability, fallback }: { capability?: Capability; fallback: string }) {
  return (
    <div className="rounded-control border border-line bg-surface-subtle p-4 text-sm text-muted" role="note">
      {capability?.reason || fallback}
    </div>
  )
}
