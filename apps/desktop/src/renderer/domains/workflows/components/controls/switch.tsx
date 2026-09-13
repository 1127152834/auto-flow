// Source: WebRPA@5ccb900e, components/ui/switch.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import * as SwitchPrimitives from '@radix-ui/react-switch'
import { cn } from '../../lib/utils'

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitives.Root>,
  React.ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>
>(({ className, ...props }, ref) => (
  <SwitchPrimitives.Root
    className={cn(
      'peer inline-flex h-[20px] w-[36px] shrink-0 cursor-pointer items-center rounded-full ' +
        'border-2 border-transparent ' +
        'transition-colors duration-200 ease-[cubic-bezier(0.25,1,0.5,1)] ' +
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] focus-visible:ring-offset-1 focus-visible:ring-offset-[hsl(var(--background))] ' +
        'disabled:cursor-not-allowed disabled:opacity-50 ' +
        // 开启：品牌蓝 + 内嵌深蓝光
        'data-[state=checked]:bg-[hsl(var(--brand-600))] ' +
        'data-[state=checked]:shadow-[inset_0_1px_3px_rgb(15_23_42_/_0.15)] ' +
        // 关闭：中性灰
        'data-[state=unchecked]:bg-[hsl(var(--slate-300))]',
      className
    )}
    {...props}
    ref={ref}
  >
    <SwitchPrimitives.Thumb
      className={cn(
        'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-soft ring-0 ' +
          'transition-transform duration-200 ease-[cubic-bezier(0.34,1.56,0.64,1)] ' +
          'data-[state=checked]:translate-x-[16px] data-[state=unchecked]:translate-x-0'
      )}
    />
  </SwitchPrimitives.Root>
))
Switch.displayName = SwitchPrimitives.Root.displayName

export { Switch }
