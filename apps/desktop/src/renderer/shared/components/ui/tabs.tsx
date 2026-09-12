import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ComponentPropsWithoutRef } from 'react'
import { cn } from '../../lib/utils'
const Tabs = ({ activationMode = 'manual', ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Root>) => <TabsPrimitive.Root activationMode={activationMode} {...props} />
const TabsList = ({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.List>) => <TabsPrimitive.List className={cn('inline-flex items-center gap-1 border-b border-line', className)} {...props} />
const TabsTrigger = ({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) => <TabsPrimitive.Trigger className={cn('min-h-10 rounded-t-control px-3 py-2 text-sm text-muted transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus disabled:text-disabled-ink disabled:cursor-not-allowed data-[state=active]:border-b-2 data-[state=active]:border-clay data-[state=active]:text-ink', className)} {...props} />
const TabsContent = ({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) => <TabsPrimitive.Content className={cn('mt-4 focus:outline-none', className)} {...props} />
export { Tabs, TabsList, TabsTrigger, TabsContent }
