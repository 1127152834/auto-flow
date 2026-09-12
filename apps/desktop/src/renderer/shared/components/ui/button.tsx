import type { ComponentPropsWithRef } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'
import { Spinner } from './spinner'

const buttonVariants = cva('af-button relative inline-flex shrink-0 items-center justify-center gap-2 rounded-control border border-transparent font-semibold transition-colors [transition-duration:var(--motion-control)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed', {
  variants: {
    variant: {
      primary: 'bg-clay text-on-accent shadow-sm enabled:hover:bg-clay-strong enabled:active:bg-clay-strong',
      secondary: 'border-control-border bg-surface text-ink enabled:hover:bg-surface-hover enabled:active:bg-clay-soft',
      ghost: 'text-muted enabled:hover:bg-surface-hover enabled:hover:text-ink enabled:active:bg-clay-soft',
      danger: 'bg-danger text-on-accent shadow-sm enabled:hover:bg-danger-strong enabled:active:bg-danger-strong',
    },
    size: { sm: 'h-[var(--control-sm)] px-3 text-xs', md: 'h-[var(--control-md)] px-4 text-sm' },
  },
  defaultVariants: { variant: 'secondary', size: 'md' },
})
export type ButtonProps = ComponentPropsWithRef<'button'> & VariantProps<typeof buttonVariants> & {
  loading?: boolean
  loadingText?: string
}

export function Button({ className, variant, size, type = 'button', disabled, loading = false, loadingText, children, ...props }: ButtonProps) {
  return <button {...props} type={type} disabled={disabled || loading} aria-busy={loading || props['aria-busy']}
    className={cn(buttonVariants({ variant, size }), className)}>
    {loading ? <Spinner size={12} className="absolute left-0.5" /> : null}
    <span className="grid min-w-0">
      <span className={cn('col-start-1 row-start-1 inline-flex min-w-0 items-center justify-center gap-2', loading && loadingText !== undefined && 'opacity-0')}>{children}</span>
      {loadingText !== undefined ? <span aria-hidden="true" className={cn('col-start-1 row-start-1', !loading && 'opacity-0')}>{loadingText}</span> : null}
    </span>
  </button>
}
