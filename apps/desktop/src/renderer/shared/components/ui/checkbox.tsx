import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
export function Checkbox({ className, ...props }: ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>) { return <CheckboxPrimitive.Root className={cn('h-4 w-4 rounded border border-line bg-surface data-[state=checked]:bg-clay', className)} {...props} /> }
