import { useId } from 'react'
import { cn } from '../../lib/utils'

/** Native group semantics and keyboard behavior with AutoFlow's own visual tokens. */
export function RadioGroup({ value, onValueChange, options, label, disabled, className }: {
  value: string
  onValueChange(value: string): void
  options: { value: string; label: string; disabled?: boolean }[]
  label: string
  disabled?: boolean
  className?: string
}) {
  const name = useId()
  return <fieldset disabled={disabled} className={cn('m-0 min-w-0 border-0 p-0', className)}>
    <legend className="sr-only">{label}</legend>
    <div className="flex flex-wrap gap-x-5 gap-y-2">
      {options.map(option => <label key={option.value} className="inline-flex min-h-8 items-center gap-2 text-sm has-[:disabled]:text-muted">
        <input type="radio" name={name} value={option.value} checked={value === option.value} disabled={disabled || option.disabled} onChange={() => onValueChange(option.value)}
          className="m-0 h-[18px] w-[18px] shrink-0 appearance-none rounded-full border border-control-border bg-surface checked:border-[5px] checked:border-clay hover:border-clay focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-clay disabled:cursor-not-allowed disabled:opacity-50" />
        {option.label}
      </label>)}
    </div>
  </fieldset>
}
