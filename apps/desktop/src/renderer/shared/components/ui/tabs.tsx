import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
const Tabs = TabsPrimitive.Root
export type TabsVariant = 'underline' | 'segmented'
type ListProps = ComponentPropsWithoutRef<typeof TabsPrimitive.List> & { variant?: TabsVariant }
type TriggerProps = ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger> & { variant?: TabsVariant }
const TabsList = ({ className, variant = 'underline', ...props }: ListProps) => <TabsPrimitive.List className={cn('inline-flex items-center gap-1', variant === 'underline' ? 'border-b border-line' : 'rounded-control border border-line bg-surface p-1', className)} {...props} />
const TabsTrigger = ({ className, variant = 'underline', ...props }: TriggerProps) => <TabsPrimitive.Trigger className={cn('text-sm text-muted', variant === 'underline' ? 'px-3 py-2 data-[state=active]:border-b-2 data-[state=active]:border-clay data-[state=active]:text-ink' : 'rounded-control px-3 py-1.5 data-[state=active]:bg-clay-soft data-[state=active]:font-medium data-[state=active]:text-clay', className)} {...props} />
const TabsContent = ({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) => <TabsPrimitive.Content className={cn('mt-4 focus:outline-none', className)} {...props} />
export { Tabs, TabsList, TabsTrigger, TabsContent }
