import * as Primitive from '@radix-ui/react-scroll-area'
import type { ComponentPropsWithRef, CSSProperties } from 'react'
import { cn } from '../../lib/utils'

type ScrollAreaProps = ComponentPropsWithRef<'div'> & { viewportClassName?: string; viewportStyle?: CSSProperties }
export function ScrollArea({ ref, children, className, style, viewportClassName, viewportStyle, ...viewportProps }: ScrollAreaProps) {
  return <Primitive.Root type="auto" className={cn('af-scroll-area relative overflow-hidden', className)} style={style}>
    <Primitive.Viewport {...viewportProps} ref={ref} tabIndex={viewportProps.tabIndex ?? 0} className={cn('h-full w-full rounded-[inherit] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus', viewportClassName)} style={viewportStyle}>{children}</Primitive.Viewport>
    {(['vertical', 'horizontal'] as const).map(orientation => <Primitive.Scrollbar key={orientation} orientation={orientation} className="af-scrollbar"><Primitive.Thumb className="af-scroll-thumb" /></Primitive.Scrollbar>)}
    <Primitive.Corner className="bg-surface-subtle" />
  </Primitive.Root>
}
