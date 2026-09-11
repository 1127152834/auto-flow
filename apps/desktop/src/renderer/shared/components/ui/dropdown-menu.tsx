import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'

const DropdownMenu = DropdownMenuPrimitive.Root
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
const DropdownMenuContent = ({ className, sideOffset = 6, ...props }: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>) => <DropdownMenuPrimitive.Portal><DropdownMenuPrimitive.Content sideOffset={sideOffset} className={cn('z-50 min-w-36 rounded-control border border-line bg-surface p-1 text-sm text-ink shadow-xl focus:outline-none', className)} {...props} /></DropdownMenuPrimitive.Portal>
const DropdownMenuItem = ({ className, ...props }: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Item>) => <DropdownMenuPrimitive.Item className={cn('flex cursor-default select-none items-center rounded-control px-3 py-2 outline-none data-[disabled]:pointer-events-none data-[highlighted]:bg-surface-hover data-[disabled]:opacity-50', className)} {...props} />
const DropdownMenuSeparator = ({ className, ...props }: ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Separator>) => <DropdownMenuPrimitive.Separator className={cn('my-1 h-px bg-line', className)} {...props} />

export { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator }
