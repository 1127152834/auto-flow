// Source: WebRPA@5ccb900e, components/ui/custom-dialogs.tsx; see SOURCE.md for license and adaptation boundaries.
import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './dialog'
import { Input } from './input'
import { Button } from './button'
import { CheckCircle2, XCircle, AlertTriangle, Info } from 'lucide-react'
import { cn } from '../../lib/utils'

// 输入弹窗组件
interface InputDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  placeholder?: string
  defaultValue?: string
  onConfirm: (value: string) => void
  onCancel?: () => void
}

export function InputDialog({
  open,
  onOpenChange,
  title,
  description,
  placeholder,
  defaultValue = '',
  onConfirm,
  onCancel,
}: InputDialogProps) {
  const [value, setValue] = useState(defaultValue)

  const handleConfirm = () => {
    onConfirm(value)
    onOpenChange(false)
    setValue('')
  }

  const handleCancel = () => {
    onCancel?.()
    onOpenChange(false)
    setValue('')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="py-1">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleConfirm()
              } else if (e.key === 'Escape') {
                handleCancel()
              }
            }}
            autoFocus
          />
        </div>
        <DialogFooter>
          <Button variant="secondary" size="sm" onClick={handleCancel}>
            取消
          </Button>
          <Button variant="success" size="sm" onClick={handleConfirm}>
            确定
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// 确认弹窗组件
interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  onConfirm: () => void
  onCancel?: () => void
  confirmText?: string
  cancelText?: string
  variant?: 'default' | 'destructive'
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  onCancel,
  confirmText = '确定',
  cancelText = '取消',
  variant = 'default',
}: ConfirmDialogProps) {
  const handleConfirm = () => {
    onConfirm()
    onOpenChange(false)
  }

  const handleCancel = () => {
    onCancel?.()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="whitespace-pre-line">
            {description}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" size="sm" onClick={handleCancel}>
            {cancelText}
          </Button>
          <Button
            variant={variant === 'default' ? 'success' : variant}
            size="sm"
            onClick={handleConfirm}
          >
            {confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// 提示弹窗组件
interface AlertDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  onConfirm?: () => void
  confirmText?: string
  variant?: 'default' | 'success' | 'error' | 'warning'
}

export function AlertDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  confirmText = '确定',
  variant = 'default',
}: AlertDialogProps) {
  const handleConfirm = () => {
    onConfirm?.()
    onOpenChange(false)
  }

  // 配色 token
  const getVariantStyles = () => {
    switch (variant) {
      case 'success':
        return {
          Icon: CheckCircle2,
          iconClass: 'text-[hsl(var(--success-600))]',
          iconBg: 'bg-[hsl(var(--success-50))] border-[hsl(var(--success-500)/0.3)] ring-[hsl(var(--success-500)/0.12)]',
          btnVariant: 'success' as const,
        }
      case 'error':
        return {
          Icon: XCircle,
          iconClass: 'text-[hsl(var(--danger-600))]',
          iconBg: 'bg-[hsl(var(--danger-50))] border-[hsl(var(--danger-500)/0.3)] ring-[hsl(var(--danger-500)/0.12)]',
          btnVariant: 'destructive' as const,
        }
      case 'warning':
        return {
          Icon: AlertTriangle,
          iconClass: 'text-[hsl(var(--warning-600))]',
          iconBg: 'bg-[hsl(var(--warning-50))] border-[hsl(var(--warning-500)/0.3)] ring-[hsl(var(--warning-500)/0.12)]',
          btnVariant: 'warning' as const,
        }
      default:
        return {
          Icon: Info,
          iconClass: 'text-[hsl(var(--brand-600))]',
          iconBg: 'bg-[hsl(var(--brand-50))] border-[hsl(var(--brand-500)/0.3)] ring-[hsl(var(--brand-500)/0.12)]',
          btnVariant: 'default' as const,
        }
    }
  }

  const { Icon, iconClass, iconBg, btnVariant } = getVariantStyles()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[440px]">
        <DialogHeader>
          <div className="flex items-start gap-3.5">
            <div className={cn(
              'shrink-0 w-10 h-10 rounded-full flex items-center justify-center border ring-[6px]',
              iconBg
            )}>
              <Icon className={cn('w-5 h-5', iconClass)} strokeWidth={2.2} />
            </div>
            <div className="flex-1 pt-1">
              <DialogTitle>{title}</DialogTitle>
              <DialogDescription className="whitespace-pre-line mt-1.5">
                {description}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <DialogFooter>
          <Button onClick={handleConfirm} variant={btnVariant} size="sm" className="w-full sm:w-auto">
            {confirmText}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
