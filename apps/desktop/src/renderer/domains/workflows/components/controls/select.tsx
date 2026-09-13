// Source: WebRPA@5ccb900e, components/ui/select.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '../../lib/utils'

const Select = SelectPrimitive.Root
const SelectGroup = SelectPrimitive.Group
const SelectValue = SelectPrimitive.Value

const SelectTrigger = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      'group flex h-8 w-full items-center justify-between gap-1.5 whitespace-nowrap rounded-[7px] ' +
        'border border-[hsl(var(--slate-200))] bg-[hsl(var(--slate-50))] px-2.5 py-1 text-[13px] ' +
        'text-[hsl(var(--foreground))] ' +
        'shadow-[inset_0_1px_2px_rgb(15_23_42_/_0.04)] ' +
        'transition-[border-color,box-shadow,background-color] duration-150 ease-[cubic-bezier(0.25,1,0.5,1)] ' +
        'hover:border-[hsl(var(--slate-300))] hover:bg-[hsl(var(--card))] ' +
        'focus:outline-none focus:border-[hsl(var(--brand-500))] focus:bg-[hsl(var(--card))] focus:ring-2 focus:ring-[hsl(var(--brand-500)/0.18)] ' +
        'data-[state=open]:border-[hsl(var(--brand-500))] data-[state=open]:bg-[hsl(var(--card))] data-[state=open]:ring-2 data-[state=open]:ring-[hsl(var(--brand-500)/0.18)] ' +
        'disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-[hsl(var(--muted))] ' +
        '[&>span]:line-clamp-1',
      className
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="h-3.5 w-3.5 opacity-60 transition-transform duration-200 group-data-[state=open]:rotate-180 group-data-[state=open]:text-[hsl(var(--brand-600))] group-data-[state=open]:opacity-100" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
))
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName

const SelectScrollUpButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.ScrollUpButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollUpButton>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollUpButton
    ref={ref}
    className={cn('flex cursor-default items-center justify-center py-1 text-[hsl(var(--muted-foreground))]', className)}
    {...props}
  >
    <ChevronUp className="h-4 w-4" />
  </SelectPrimitive.ScrollUpButton>
))
SelectScrollUpButton.displayName = SelectPrimitive.ScrollUpButton.displayName

const SelectScrollDownButton = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.ScrollDownButton>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.ScrollDownButton>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.ScrollDownButton
    ref={ref}
    className={cn('flex cursor-default items-center justify-center py-1 text-[hsl(var(--muted-foreground))]', className)}
    {...props}
  >
    <ChevronDown className="h-4 w-4" />
  </SelectPrimitive.ScrollDownButton>
))
SelectScrollDownButton.displayName = SelectPrimitive.ScrollDownButton.displayName

const SelectContent = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = 'popper', ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        'relative z-50 max-h-96 min-w-[10rem] overflow-hidden rounded-[10px] ' +
          'border border-[hsl(var(--border))] bg-[hsl(var(--popover))] text-[hsl(var(--popover-foreground))] ' +
          'shadow-pop-xl backdrop-blur-md ' +
          'data-[state=open]:animate-in data-[state=closed]:animate-out ' +
          'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 ' +
          'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 ' +
          'data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2 ' +
          'duration-150',
        position === 'popper' &&
          'data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1',
        className
      )}
      position={position}
      {...props}
    >
      <SelectScrollUpButton />
      <SelectPrimitive.Viewport
        className={cn(
          'p-1.5',
          position === 'popper' &&
            'h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]'
        )}
      >
        {children}
      </SelectPrimitive.Viewport>
      <SelectScrollDownButton />
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
))
SelectContent.displayName = SelectPrimitive.Content.displayName

const SelectLabel = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Label>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.Label
    ref={ref}
    className={cn('px-2 py-1.5 text-[10px] uppercase tracking-wider font-semibold text-[hsl(var(--muted-foreground))]', className)}
    {...props}
  />
))
SelectLabel.displayName = SelectPrimitive.Label.displayName

const SelectItem = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex w-full cursor-pointer select-none items-center rounded-[6px] py-1.5 pl-2.5 pr-7 text-[13px] outline-none ' +
        'transition-[background-color,color] duration-100 ' +
        'hover:bg-[hsl(var(--brand-50))] hover:text-[hsl(var(--brand-700))] ' +
        'focus:bg-[hsl(var(--brand-50))] focus:text-[hsl(var(--brand-700))] ' +
        'data-[state=checked]:bg-[hsl(var(--brand-100))] data-[state=checked]:text-[hsl(var(--brand-800))] data-[state=checked]:font-medium ' +
        'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      className
    )}
    {...props}
  >
    <span className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="h-3.5 w-3.5 text-[hsl(var(--brand-600))]" strokeWidth={2.5} />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
))
SelectItem.displayName = SelectPrimitive.Item.displayName

const SelectSeparator = React.forwardRef<
  React.ElementRef<typeof SelectPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Separator>
>(({ className, ...props }, ref) => (
  <SelectPrimitive.Separator
    ref={ref}
    className={cn('mx-1 my-1 h-px bg-[hsl(var(--border))]', className)}
    {...props}
  />
))
SelectSeparator.displayName = SelectPrimitive.Separator.displayName

export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
  SelectScrollUpButton,
  SelectScrollDownButton,
}

export default Select
