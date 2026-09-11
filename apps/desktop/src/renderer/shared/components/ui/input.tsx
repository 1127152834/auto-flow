import type { InputHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn('h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none transition-shadow placeholder:text-muted focus:border-clay focus:ring-2 focus:ring-clay/15 disabled:cursor-not-allowed disabled:opacity-50', className)} {...props} />
}
