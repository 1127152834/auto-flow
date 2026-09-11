import type { ButtonHTMLAttributes } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-clay text-white shadow-sm hover:bg-clay-strong',
  secondary: 'border border-line bg-surface text-ink hover:bg-surface-hover',
  ghost: 'text-muted hover:bg-surface-hover hover:text-ink',
}

export function Button({ className = '', variant = 'secondary', ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-control px-4 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-clay disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    />
  )
}
