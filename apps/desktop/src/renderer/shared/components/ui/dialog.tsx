import * as DialogPrimitive from '@radix-ui/react-dialog'
import { createContext, useContext, type ComponentPropsWithoutRef, type ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { OverlayHostContext, useOverlayFrame } from './overlay-host'

const BusyContext = createContext(false)
type RootProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Root> & { busy?: boolean }
const Dialog = ({ busy = false, children, onOpenChange, ...props }: RootProps) => <BusyContext.Provider value={busy}><DialogPrimitive.Root {...props} onOpenChange={(nextOpen) => { if (busy && !nextOpen) return; onOpenChange?.(nextOpen) }}>{children}</DialogPrimitive.Root></BusyContext.Provider>
const DialogTrigger = DialogPrimitive.Trigger
function DialogClose({ onClick, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Close>) {
  const busy = useContext(BusyContext)
  return <DialogPrimitive.Close {...props} onClick={(event) => { if (busy) { event.preventDefault(); return }; onClick?.(event) }} />
}
const DialogTitle = ({ className, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Title>) => <DialogPrimitive.Title className={cn('text-lg font-semibold text-ink', className)} {...props} />
const DialogDescription = ({ className, ...props }: ComponentPropsWithoutRef<typeof DialogPrimitive.Description>) => <DialogPrimitive.Description className={cn('text-sm text-muted', className)} {...props} />
type ContentProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & { busy?: boolean; children?: ReactNode }
function DialogContent({ className, style, busy: contentBusy, onEscapeKeyDown, onPointerDownOutside, children, ...props }: ContentProps) {
  const frame = useOverlayFrame()
  const contextBusy = useContext(BusyContext)
  const busy = contentBusy ?? contextBusy
  return <OverlayHostContext.Provider value={frame.scope}><DialogPrimitive.Portal>
    <DialogPrimitive.Overlay data-slot="modal-overlay" style={frame.overlayStyle} className="autoflow-dialog-overlay fixed inset-0 bg-[var(--color-overlay)]" />
    <DialogPrimitive.Content data-overlay-depth={frame.scope.depth} style={{ ...style, ...frame.contentStyle }} className={cn('autoflow-dialog-content fixed left-1/2 top-1/2 grid w-[min(92vw,32rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-modal border border-line bg-surface p-6 shadow-modal focus:outline-none motion-safe:transition-all', className)} onEscapeKeyDown={(event) => { if (busy || frame.hasOpenPopup()) { event.preventDefault(); return }; onEscapeKeyDown?.(event) }} onPointerDownOutside={(event) => { if (busy) { event.preventDefault(); return }; onPointerDownOutside?.(event) }} {...props}>{children}<div data-overlay-host ref={frame.hostRef} style={{ display: 'contents' }} /></DialogPrimitive.Content>
  </DialogPrimitive.Portal></OverlayHostContext.Provider>
}
export { Dialog, DialogTrigger, DialogClose, DialogContent, DialogTitle, DialogDescription }
