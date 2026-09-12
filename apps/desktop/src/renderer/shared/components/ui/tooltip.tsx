import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import type { ComponentPropsWithoutRef } from 'react'
import { useOverlayHost } from './overlay-host'
import { cn } from '../../lib/utils'
const TooltipProvider = ({ delayDuration = 400, ...props }: ComponentPropsWithoutRef<typeof TooltipPrimitive.Provider>) => <TooltipPrimitive.Provider delayDuration={delayDuration} {...props} />
const Tooltip = TooltipPrimitive.Root
const TooltipTrigger = TooltipPrimitive.Trigger
function TooltipContent({ className, style, sideOffset = 6, ...props }: ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>) {
  const host = useOverlayHost()
  return <TooltipPrimitive.Portal container={host.container}><TooltipPrimitive.Content data-af-tooltip sideOffset={sideOffset} collisionPadding={12} style={{...style,...host.style}} className={cn('af-tooltip-motion max-w-72 break-words rounded-control border border-ink bg-ink px-3 py-2 text-xs text-on-accent shadow-popup',className)} {...props} /></TooltipPrimitive.Portal>
}
export { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent }
