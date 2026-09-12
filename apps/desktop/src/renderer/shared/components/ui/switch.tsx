import * as SwitchPrimitive from '@radix-ui/react-switch'
import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'

export type SwitchProps = ComponentPropsWithRef<typeof SwitchPrimitive.Root>
export function Switch({ className, ...props }: SwitchProps) {
  return <SwitchPrimitive.Root {...props} data-af-choice="switch" className={cn('af-choice', className)}>
    <span data-af-choice-mark aria-hidden="true"><SwitchPrimitive.Thumb data-af-choice-thumb /></span>
  </SwitchPrimitive.Root>
}
