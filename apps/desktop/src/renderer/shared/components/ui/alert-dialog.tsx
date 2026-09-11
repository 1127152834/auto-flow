import * as AlertDialogPrimitive from '@radix-ui/react-alert-dialog'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
const AlertDialog = AlertDialogPrimitive.Root
const AlertDialogTrigger = AlertDialogPrimitive.Trigger
const AlertDialogCancel = AlertDialogPrimitive.Cancel
const AlertDialogAction = AlertDialogPrimitive.Action
const AlertDialogTitle = AlertDialogPrimitive.Title
const AlertDialogDescription = AlertDialogPrimitive.Description
const AlertDialogContent = ({ className, ...props }: ComponentPropsWithoutRef<typeof AlertDialogPrimitive.Content>) => <AlertDialogPrimitive.Portal><AlertDialogPrimitive.Overlay data-slot="modal-overlay" className="fixed inset-0 z-[50] bg-ink/35" /><AlertDialogPrimitive.Content className={cn('fixed left-1/2 top-1/2 z-[50] grid w-[min(92vw,30rem)] -translate-x-1/2 -translate-y-1/2 gap-4 rounded-card border border-line bg-surface p-6 shadow-xl', className)} {...props} /></AlertDialogPrimitive.Portal>
export { AlertDialog, AlertDialogTrigger, AlertDialogCancel, AlertDialogAction, AlertDialogTitle, AlertDialogDescription, AlertDialogContent }
