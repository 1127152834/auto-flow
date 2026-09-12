import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
export function Skeleton({className,...props}:HTMLAttributes<HTMLDivElement>){return <div aria-hidden="true" {...props} className={cn('rounded-control bg-surface-subtle motion-safe:animate-pulse',className)}/>}
