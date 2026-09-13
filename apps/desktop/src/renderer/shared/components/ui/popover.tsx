import * as Primitive from '@radix-ui/react-popover'
import { useRef, type ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
import { useOverlayHost } from './overlay-host'

export const Popover = Primitive.Root
export const PopoverTrigger = Primitive.Trigger
export const PopoverClose = Primitive.Close

/** Non-modal forms use the same portal host as the containing dialog. */
export function PopoverContent({ className, style, onCloseAutoFocus, ...props }: ComponentPropsWithoutRef<typeof Primitive.Content>) {
  const host = useOverlayHost()
  const trigger = useRef<HTMLElement | null>(null)
  return <Primitive.Portal container={host.container}>
    <Primitive.Content ref={node => {
      if (node?.id) trigger.current = Array.from(document.querySelectorAll<HTMLElement>('[aria-controls]')).find(item => item.getAttribute('aria-controls') === node.id) ?? null
    }} onCloseAutoFocus={event => {
      onCloseAutoFocus?.(event)
      if (!event.defaultPrevented && trigger.current?.isConnected) { event.preventDefault(); trigger.current.focus() }
    }} data-af-popup sideOffset={6} align="start" collisionPadding={12} {...props}
      style={{ ...style, ...host.style }}
      className={cn('max-h-[var(--radix-popover-content-available-height)] w-[min(32rem,calc(100vw-2rem))] max-w-[var(--radix-popover-content-available-width)] overflow-auto rounded-card border border-line bg-surface p-4 text-ink shadow-modal outline-none', className)} />
  </Primitive.Portal>
}
