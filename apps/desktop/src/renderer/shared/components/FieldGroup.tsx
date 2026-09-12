import { useId, type ComponentPropsWithRef, type ReactNode } from 'react'
import { cn } from '../lib/utils'

type FieldGroupProps = ComponentPropsWithRef<'fieldset'> & { legend: ReactNode; error?: string; hint?: string }
export function FieldGroup({ legend, error, hint, id, className, children, ...props }: FieldGroupProps) {
  const generatedId = useId()
  const groupId = id ?? generatedId
  const descriptionId = error ? `${groupId}-error` : hint ? `${groupId}-hint` : undefined
  return <fieldset {...props} id={groupId} aria-invalid={error ? true : props['aria-invalid']}
    aria-describedby={[props['aria-describedby'], descriptionId].filter(Boolean).join(' ') || undefined}
    className={cn('m-0 grid min-w-0 gap-3 border-0 p-0', className)}>
    <legend className="mb-2 text-sm font-medium text-ink">{legend}</legend>
    {children}
    {error ? <p id={descriptionId} role="alert" className="text-xs text-danger">{error}</p> : hint ? <p id={descriptionId} className="text-xs text-muted">{hint}</p> : null}
  </fieldset>
}
