import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
const Tabs = TabsPrimitive.Root
const TabsList = ({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.List>) => <TabsPrimitive.List className={cn('inline-flex items-center gap-1 border-b border-line', className)} {...props} />
const TabsTrigger = ({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) => <TabsPrimitive.Trigger className={cn('px-3 py-2 text-sm text-muted data-[state=active]:border-b-2 data-[state=active]:border-clay data-[state=active]:text-ink', className)} {...props} />
const TabsContent = ({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) => <TabsPrimitive.Content className={cn('mt-4 focus:outline-none', className)} {...props} />
export { Tabs, TabsList, TabsTrigger, TabsContent }
