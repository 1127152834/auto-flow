import { X } from '@phosphor-icons/react/X'
import { useId, useRef, type PropsWithChildren, type ReactNode } from 'react'
import { Button } from './ui/button'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from './ui/dialog'
import { cn } from '../lib/utils'

type ModalProps = PropsWithChildren<{
  open: boolean
  onOpenChange(open: boolean): void
  title: string
  description?: string
  footer?: ReactNode
  size?: 'small' | 'medium' | 'large'
  variant?: 'default' | 'form' | 'split'
  closeDisabled?: boolean
  bodyClassName?: string
}>

const sizes = {
  small: 'max-w-md',
  medium: 'max-w-2xl',
  large: 'max-w-5xl',
}

export function Modal({ open, onOpenChange, title, description, children, footer, size = 'medium', variant = 'default', closeDisabled = false, bodyClassName }: ModalProps) {
  const descriptionId = useId()
  const focusReturn = useRef<{ opener: HTMLElement | null; container: HTMLElement | null; content: HTMLElement | null }>({ opener: null, container: null, content: null })

  const captureReturnTarget = (candidate: EventTarget | null, content: HTMLElement) => {
    if (focusReturn.current.content !== content) focusReturn.current = { opener: null, container: null, content }
    if (focusReturn.current.opener || !(candidate instanceof HTMLElement) || candidate === document.body || !candidate.isConnected || content.contains(candidate) || candidate.closest('[hidden], [inert]')) return
    focusReturn.current.opener = candidate
    focusReturn.current.container = candidate.closest<HTMLElement>('[role="dialog"], main, [role="main"]')
  }

  return <Dialog open={open} onOpenChange={onOpenChange} busy={closeDisabled}>
    <DialogContent
      busy={closeDisabled}
      aria-describedby={description ? descriptionId : undefined}
      className={cn('max-h-[min(90vh,56rem)] w-[min(94vw,64rem)] grid-rows-[auto_minmax(0,1fr)_auto] p-0', sizes[size])}
      onFocusCapture={(event) => captureReturnTarget(event.relatedTarget, event.currentTarget)}
      onOpenAutoFocus={(event) => {
        if (event.target instanceof HTMLElement) captureReturnTarget(document.activeElement, event.target)
      }}
      onCloseAutoFocus={(event) => {
        event.preventDefault()
        if (focusReturn.current.content !== event.target) return
        const { opener, container } = focusReturn.current
        focusReturn.current = { opener: null, container: null, content: null }
        if (opener?.isConnected && !opener.matches(':disabled') && !opener.closest('[hidden], [inert]')) {
          opener.focus({ preventScroll: true })
          if (document.activeElement === opener) return
        }
        if (document.activeElement instanceof HTMLElement && document.activeElement !== document.body) return
        if (container?.isConnected && !container.closest('[hidden], [inert]')) {
          const tabIndex = container.getAttribute('tabindex')
          if (tabIndex == null) container.setAttribute('tabindex', '-1')
          container.focus({ preventScroll: true })
          if (tabIndex == null) container.removeAttribute('tabindex')
        }
      }}
    >
      <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
        <div className="grid gap-1">
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription id={descriptionId}>{description}</DialogDescription> : null}
        </div>
        <DialogClose asChild>
          <Button type="button" variant="ghost" disabled={closeDisabled} aria-label={closeDisabled ? '正在处理，请稍候' : '关闭'} title={closeDisabled ? '正在处理，请稍候' : '关闭'} className="h-9 w-9 shrink-0 p-0">
            <X size={18} />
          </Button>
        </DialogClose>
      </header>
      <div role="region" aria-label={`${title}内容`} tabIndex={0} className={cn('min-h-0 overflow-y-auto px-6 py-5', variant === 'form' && 'bg-surface-subtle', variant === 'split' && 'grid gap-6 md:grid-cols-2', bodyClassName)}>
        {children}
      </div>
      {footer ? <footer className="flex justify-end gap-3 border-t border-line px-6 py-4">{footer}</footer> : null}
    </DialogContent>
  </Dialog>
}
