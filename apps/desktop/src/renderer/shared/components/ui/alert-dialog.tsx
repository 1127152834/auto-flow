import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
import { OverlayHostContext, useOverlayFrame } from './overlay-host'
const AlertDialog = AlertDialogPrimitive.Root
const AlertDialogTrigger = AlertDialogPrimitive.Trigger
const AlertDialogCancel = AlertDialogPrimitive.Cancel
const AlertDialogAction = AlertDialogPrimitive.Action
const AlertDialogTitle = ({className,...props}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Title>) => <AlertDialogPrimitive.Title className={cn('text-lg font-semibold text-ink',className)} {...props}/>
const AlertDialogDescription = ({className,...props}: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Description>) => <AlertDialogPrimitive.Description className={cn('text-sm text-muted',className)} {...props}/>
function AlertDialogContent({ className, style, children, onEscapeKeyDown, ...props }: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Content>) {
  const frame = useOverlayFrame()
  return <OverlayHostContext.Provider value={frame.scope}><AlertDialogPrimitive.Portal>
    <AlertDialogPrimitive.Overlay data-slot="modal-overlay" style={frame.overlayStyle} className="fixed inset-0 z-[50] bg-ink/35" />
    <AlertDialogPrimitive.Content data-overlay-depth={frame.scope.depth} onEscapeKeyDown={event => { if (frame.hasOpenPopup()) { event.preventDefault(); return }; onEscapeKeyDown?.(event) }} style={{ ...style, ...frame.contentStyle }} className={cn('fixed left-1/2 top-1/2 z-[50] grid w-[min(92vw,30rem)] -translate-x-1/2 -translate-y-1/2 max-h-[90dvh] overflow-y-auto gap-4 rounded-card border border-line bg-surface p-6 shadow-xl', className)} {...props}>
      {children}<div data-overlay-host ref={frame.hostRef} style={{ display: 'contents' }} />
    </AlertDialogPrimitive.Content>
  </AlertDialogPrimitive.Portal></OverlayHostContext.Provider>
}

export { AlertDialog, AlertDialogTrigger, AlertDialogCancel, AlertDialogAction, AlertDialogTitle, AlertDialogDescription, AlertDialogContent }
