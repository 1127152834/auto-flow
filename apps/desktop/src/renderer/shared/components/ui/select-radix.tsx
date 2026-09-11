import * as SelectPrimitive from '@radix-ui/react-select'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'

const Select = SelectPrimitive.Root
const SelectGroup = SelectPrimitive.Group
const SelectValue = SelectPrimitive.Value
const SelectTrigger = ({ className, ...props }: ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>) => <SelectPrimitive.Trigger className={cn('flex h-10 w-full items-center justify-between rounded-control border border-line bg-surface px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-clay/15', className)} {...props} />
const SelectContent = ({ className, ...props }: ComponentPropsWithoutRef<typeof SelectPrimitive.Content>) => <SelectPrimitive.Portal><SelectPrimitive.Content className={cn('z-50 overflow-hidden rounded-control border border-line bg-surface p-1 shadow-lg', className)} {...props} /></SelectPrimitive.Portal>
const SelectItem = ({ className, ...props }: ComponentPropsWithoutRef<typeof SelectPrimitive.Item>) => <SelectPrimitive.Item className={cn('cursor-pointer rounded px-3 py-2 text-sm text-ink outline-none focus:bg-surface-hover', className)} {...props} />
const SelectLabel = SelectPrimitive.Label
const SelectSeparator = SelectPrimitive.Separator
export { Select, SelectGroup, SelectValue, SelectTrigger, SelectContent, SelectItem, SelectLabel, SelectSeparator }
