import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>

const buttonVariants = cva('inline-flex h-10 items-center justify-center gap-2 rounded-control px-4 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-clay disabled:cursor-not-allowed disabled:opacity-50', {
  variants: { variant: { primary: 'bg-clay text-white shadow-sm hover:bg-clay-strong', secondary: 'border border-line bg-surface text-ink hover:bg-surface-hover', ghost: 'text-muted hover:bg-surface-hover hover:text-ink' } },
  defaultVariants: { variant: 'secondary' },
})

export function Button({ className, variant, ...props }: ButtonProps) {
  return <button className={cn(buttonVariants({ variant }), className)} {...props} />
}
