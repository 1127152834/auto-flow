import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'

type TextareaProps = ComponentPropsWithRef<'textarea'> & { size?: 'sm' | 'md' }
export function Textarea({ className, size = 'md', ...props }: TextareaProps) {
  return <textarea {...props} data-af-control className={cn('min-h-24 w-full min-w-0 px-3 py-2', size === 'sm' ? 'text-xs' : 'text-sm', className)} />
}
