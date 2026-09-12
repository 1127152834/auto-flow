import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import { Check, Minus } from '@phosphor-icons/react'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'

export type CheckboxProps = ComponentPropsWithRef<typeof CheckboxPrimitive.Root>
export function Checkbox({ className, ...props }: CheckboxProps) {
  return <CheckboxPrimitive.Root {...props} data-af-choice="checkbox" className={cn('af-choice', className)}>
    <span data-af-choice-mark aria-hidden="true">
      <CheckboxPrimitive.Indicator>
        <Check data-af-choice-glyph="checked" size={14} weight="bold" />
        <Minus data-af-choice-glyph="mixed" size={14} weight="bold" />
      </CheckboxPrimitive.Indicator>
    </span>
  </CheckboxPrimitive.Root>
}
