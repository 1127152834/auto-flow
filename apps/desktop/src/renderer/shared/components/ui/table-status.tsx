import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'

export function TableStatus({ tone = 'neutral', className, children, ...props }: ComponentPropsWithRef<'span'> & { tone?: 'neutral' | 'success' | 'warning' | 'danger' }) {
  return <span {...props} data-table-status={tone} className={cn('af-table-status', className)}><span aria-hidden="true" className="af-table-status-dot" />{children}</span>
}
