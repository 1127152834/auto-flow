import type { SelectHTMLAttributes } from 'react'

export function Select({ className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink outline-none focus:border-clay focus:ring-2 focus:ring-clay/15 ${className}`} {...props} />
}
