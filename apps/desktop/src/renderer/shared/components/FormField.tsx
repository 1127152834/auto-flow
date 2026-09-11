import { Children, cloneElement, isValidElement, type ReactNode } from 'react'
import { cn } from '../lib/utils'

type FormFieldProps = { label: string; error?: string; hint?: string; htmlFor: string; children: ReactNode; className?: string }

export function FormField({ label, error, hint, htmlFor, children, className }: FormFieldProps) {
  const descriptionId = error ? `${htmlFor}-error` : hint ? `${htmlFor}-hint` : undefined
  const control = Children.map(children, (child) => isValidElement(child) ? cloneElement(child, { id: htmlFor, 'aria-invalid': error ? true : undefined, 'aria-describedby': descriptionId } as Record<string, unknown>) : child)
  return <div className={cn('grid gap-2', className)}>
    <label className="text-sm font-medium text-ink" htmlFor={htmlFor}>{label}</label>
    {control}
    {hint && !error ? <p className="text-xs text-muted" id={`${htmlFor}-hint`}>{hint}</p> : null}
    {error ? <p className="text-xs text-clay" id={`${htmlFor}-error`} role="alert">{error}</p> : null}
  </div>
}
