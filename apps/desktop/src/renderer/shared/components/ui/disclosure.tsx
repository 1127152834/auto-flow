import { CaretRight } from '@phosphor-icons/react'
import type { ComponentPropsWithRef, ReactNode } from 'react'
import { cn } from '../../lib/utils'

export type DisclosureProps = ComponentPropsWithRef<'details'> & { summary: ReactNode }
export function Disclosure({ summary, className, children, ...props }: DisclosureProps) {
  return <details {...props} className={cn('af-disclosure min-w-0 rounded-control border border-line bg-surface-subtle text-sm text-ink', className)}>
    <summary className="flex min-h-10 cursor-pointer items-center gap-2 rounded-control px-3 py-2 font-medium">
      <CaretRight aria-hidden="true" size={16} className="af-disclosure-chevron shrink-0" />
      <span className="min-w-0 break-words">{summary}</span>
    </summary>
    <div className="px-3 pb-3 pt-1 leading-6 break-words">{children}</div>
  </details>
}
