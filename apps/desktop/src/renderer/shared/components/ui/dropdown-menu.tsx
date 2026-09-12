import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import type { ComponentPropsWithoutRef } from 'react'
import { useOverlayHost } from './overlay-host'
import { cn } from '../../lib/utils'

const DropdownMenu = DropdownMenuPrimitive.Root
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
function DropdownMenuContent({ className, style, sideOffset = 6, ...props }: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>) {
  const host = useOverlayHost()
  return <DropdownMenuPrimitive.Portal container={host.container}><DropdownMenuPrimitive.Content data-af-popup sideOffset={sideOffset} collisionPadding={12} style={{...style,...host.style}} className={cn('af-popup-motion min-w-36 max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto rounded-control border border-control-border bg-surface p-1 text-sm text-ink shadow-popup focus:outline-none', className)} {...props} /></DropdownMenuPrimitive.Portal>
}
const DropdownMenuItem = ({ className, tone, ...props }: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item> & {tone?: 'default' | 'danger'}) => <DropdownMenuPrimitive.Item className={cn(tone === 'danger' && 'text-danger', 'flex min-h-8 cursor-default select-none items-center rounded-control px-3 py-2 outline-none data-[disabled]:pointer-events-none data-[highlighted]:bg-surface-hover data-[disabled]:text-disabled-ink', className)} {...props} />
const DropdownMenuSeparator = ({ className, ...props }: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>) => <DropdownMenuPrimitive.Separator className={cn('my-1 h-px bg-line', className)} {...props} />

export { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator }
