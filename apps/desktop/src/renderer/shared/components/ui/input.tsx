import type { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none transition-shadow placeholder:text-muted focus:border-clay focus:ring-2 focus:ring-clay/15 ${className}`} {...props} />
}
