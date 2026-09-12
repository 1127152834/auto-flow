import * as RadioPrimitive from '@radix-ui/react-radio-group'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'

export type RadioGroupProps = ComponentPropsWithRef<typeof RadioPrimitive.Root>
export type RadioGroupItemProps = ComponentPropsWithRef<typeof RadioPrimitive.Item>
export function RadioGroup({ className, ...props }: RadioGroupProps) {
  return <RadioPrimitive.Root {...props} className={cn('grid gap-2', className)} />
}
export function RadioGroupItem({ className, ...props }: RadioGroupItemProps) {
  return <RadioPrimitive.Item {...props} data-af-choice="radio" className={cn('af-choice', className)}>
    <span data-af-choice-mark aria-hidden="true"><RadioPrimitive.Indicator data-af-choice-dot /></span>
  </RadioPrimitive.Item>
}
