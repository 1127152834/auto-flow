import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
const TooltipProvider = TooltipPrimitive.Provider
const Tooltip = TooltipPrimitive.Root
const TooltipTrigger = TooltipPrimitive.Trigger
const TooltipContent = ({ className, ...props }: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) => <TooltipPrimitive.Portal><TooltipPrimitive.Content className={cn('z-50 rounded px-2 py-1 text-xs text-white bg-ink', className)} {...props} /></TooltipPrimitive.Portal>
export { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent }
