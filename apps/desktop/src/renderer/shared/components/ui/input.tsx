import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'

export type InputProps = Omit<ComponentPropsWithRef<'input'>, 'size'> & { size?: 'sm' | 'md' }
export function Input({ className, size = 'md', ...props }: InputProps) {
  return <input {...props} data-af-control className={cn('w-full min-w-0 px-3', size === 'sm' ? 'h-[var(--control-sm)] text-xs' : 'h-[var(--control-md)] text-sm', className)} />
}
