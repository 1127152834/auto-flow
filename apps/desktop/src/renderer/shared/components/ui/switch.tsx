import * as SwitchPrimitive from '@radix-ui/react-switch'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
export function Switch({ className, ...props }: ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>) { return <SwitchPrimitive.Root className={cn('h-6 w-11 rounded-full bg-line data-[state=checked]:bg-clay', className)} {...props}><SwitchPrimitive.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-white transition-transform data-[state=checked]:translate-x-[22px]" /></SwitchPrimitive.Root> }
