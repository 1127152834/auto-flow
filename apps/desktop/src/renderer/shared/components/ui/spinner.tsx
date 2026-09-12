import { CircleNotch } from '@phosphor-icons/react'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/utils'

export function Spinner({ className, size = 16, ...props }: ComponentProps<typeof CircleNotch>) {
  return <CircleNotch {...props} size={size} aria-hidden="true" focusable="false" className={cn('af-spinner shrink-0', className)} />
}
