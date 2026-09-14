import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'

/** Each control keeps its own keyboard and query behavior. */
export function TableToolbar({ label, className, ...props }: ComponentPropsWithRef<'div'> & { label: string }) {
  return <div role="group" aria-label={label} {...props} className={cn('af-table-toolbar flex min-w-0 flex-wrap items-center gap-2', className)} />
}
