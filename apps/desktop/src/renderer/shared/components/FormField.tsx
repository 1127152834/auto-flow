import { Children, cloneElement, isValidElement, type ReactNode } from 'react'
import { cn } from '../lib/utils'

export type FieldA11y = { id: string; 'aria-invalid'?: boolean; 'aria-describedby'?: string }

type FormFieldProps = { label: string; error?: string; hint?: string; htmlFor: string; children: ReactNode | ((a11y: FieldA11y) => ReactNode); className?: string }

export function FormField({ label, error, hint, htmlFor, children, className }: FormFieldProps) {
  const descriptionId = error ? `${htmlFor}-error` : hint ? `${htmlFor}-hint` : undefined
  const a11y: FieldA11y = { id: htmlFor, 'aria-invalid': error ? true : undefined, 'aria-describedby': descriptionId }
  // Temporary legacy children path; domain slices migrate to explicit binding before T12.
  const control = typeof children === 'function' ? children(a11y) : Children.map(children, (child) => isValidElement(child) ? cloneElement(child, a11y as Record<string, unknown>) : child)
  return <div className={cn('grid content-start gap-2', className)}>
    <label className="text-sm font-medium text-ink" htmlFor={htmlFor}>{label}</label>
    {control}
    {hint && !error ? <p className="text-xs text-muted" id={`${htmlFor}-hint`}>{hint}</p> : null}
    {error ? <p className="text-xs text-danger" id={`${htmlFor}-error`} role="alert">{error}</p> : null}
  </div>
}
