// Source: WebRPA@5ccb900e, components/ui/label.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import { cn } from '../../lib/utils'

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean
}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, children, required, ...props }, ref) => {
    return (
      <label
        ref={ref}
        className={cn(
          'inline-flex items-center gap-1 text-[12px] font-medium leading-none ' +
            'text-[hsl(var(--slate-800))] peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
          className
        )}
        {...props}
      >
        {children}
        {required && (
          <span className="text-[hsl(var(--danger-500))] font-bold" aria-hidden="true">
            *
          </span>
        )}
      </label>
    )
  }
)
Label.displayName = 'Label'

export { Label }
