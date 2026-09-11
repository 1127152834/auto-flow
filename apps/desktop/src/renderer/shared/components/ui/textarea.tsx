import type { TextareaHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn('min-h-24 w-full resize-y rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink outline-none transition-shadow placeholder:text-muted focus:border-clay focus:ring-2 focus:ring-clay/15 disabled:cursor-not-allowed disabled:opacity-50', className)} {...props} />
}
