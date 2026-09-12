import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export function Badge({ className, tone = 'info', ...props }: HTMLAttributes<HTMLSpanElement> & {tone?: 'info' | 'success' | 'warning' | 'error' | 'neutral'}) {
  return <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', tone === 'success' ? 'bg-success/10 text-success' : tone === 'error' ? 'bg-danger/10 text-danger' : tone === 'warning' ? 'bg-warning/10 text-warning' : tone === 'neutral' ? 'bg-surface-subtle text-muted' : 'bg-clay-soft text-clay', className)} {...props} />
}
