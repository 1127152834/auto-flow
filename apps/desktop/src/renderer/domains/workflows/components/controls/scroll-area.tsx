// Source: WebRPA@5ccb900e, components/ui/scroll-area.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import { cn } from '../../lib/utils'

type ScrollAreaProps = React.HTMLAttributes<HTMLDivElement>

const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative overflow-auto scroll-smooth',
        // 平滑滚动 + 自定义滚动条样式由全局 CSS 提供
        className
      )}
      style={{ scrollBehavior: 'smooth' }}
      {...props}
    >
      {children}
    </div>
  )
)
ScrollArea.displayName = 'ScrollArea'

export { ScrollArea }
