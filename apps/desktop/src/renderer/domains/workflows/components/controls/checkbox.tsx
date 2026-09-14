// Source: WebRPA@5ccb900e, components/ui/checkbox.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import { cn } from '../../lib/utils'
import { Check } from 'lucide-react'

export interface CheckboxProps {
  id?: string
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(
  ({ id, checked = false, onCheckedChange, disabled, className }, ref) => {
    return (
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        id={id}
        ref={ref}
        disabled={disabled}
        onClick={() => !disabled && onCheckedChange?.(!checked)}
        className={cn(
          'h-4 w-4 shrink-0 rounded-control border ' +
            'flex items-center justify-center cursor-pointer ' +
            'transition-[background-color,border-color,transform,box-shadow] duration-150 ease-[cubic-bezier(0.25,1,0.5,1)] ' +
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] focus-visible:ring-offset-1 focus-visible:ring-offset-[hsl(var(--background))] ' +
            'disabled:cursor-not-allowed disabled:opacity-50 ' +
            'active:scale-90',
          checked
            ? 'bg-[hsl(var(--brand-600))] border-[hsl(var(--brand-600))] shadow-soft hover:bg-[hsl(var(--brand-700))] hover:border-[hsl(var(--brand-700))]'
            : 'bg-[hsl(var(--card))] border-[hsl(var(--slate-300))] hover:border-[hsl(var(--brand-500))] hover:bg-[hsl(var(--brand-50))]',
          className
        )}
      >
        {checked && (
          <Check
            className="h-3 w-3 text-white animate-scale-in"
            strokeWidth={3.5}
          />
        )}
      </button>
    )
  }
)
Checkbox.displayName = 'Checkbox'

export { Checkbox }
