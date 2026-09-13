// Source: WebRPA@5ccb900e, components/ui/textarea.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import { cn } from '../../lib/utils'

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          'flex min-h-[76px] w-full rounded-[7px] px-2.5 py-2 text-[13px] ' +
            'border border-[hsl(var(--slate-200))] bg-[hsl(var(--slate-50))] ' +
            'text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] ' +
            'shadow-[inset_0_1px_2px_rgb(15_23_42_/_0.04)] ' +
            'transition-[border-color,box-shadow,background-color] duration-150 ease-[cubic-bezier(0.25,1,0.5,1)] ' +
            'resize-y leading-relaxed ' +
            'hover:border-[hsl(var(--slate-300))] hover:bg-[hsl(var(--card))] ' +
            'focus-visible:outline-none focus-visible:border-[hsl(var(--brand-500))] focus-visible:bg-[hsl(var(--card))] focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500)/0.18)] ' +
            'disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-[hsl(var(--muted))] ' +
            'aria-[invalid=true]:border-[hsl(var(--danger-500))] aria-[invalid=true]:ring-[hsl(var(--danger-500)/0.18)]',
          className
        )}
        {...props}
      />
    )
  }
)
Textarea.displayName = 'Textarea'

export { Textarea }
