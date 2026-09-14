// Source: WebRPA@5ccb900e, components/ui/slider.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from "react"
import { cn } from "../../lib/utils"

interface SliderProps extends Pick<React.InputHTMLAttributes<HTMLInputElement>, "id" | "aria-label" | "aria-labelledby"> {
  value: number[]
  max?: number
  min?: number
  step?: number
  onValueChange?: (value: number[]) => void
  className?: string
  disabled?: boolean
}

const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ value, max = 100, min = 0, step = 1, onValueChange, className, disabled, ...inputProps }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = parseFloat(e.target.value)
      onValueChange?.([newValue])
    }

    const percentage = ((value[0] - min) / (max - min)) * 100

    return (
      <div
        className={cn(
          "relative flex w-full touch-none select-none items-center group",
          disabled && "opacity-50 cursor-not-allowed",
          className
        )}
      >
        {/* 轨道 */}
        <div className="relative h-[5px] w-full grow overflow-hidden rounded-full bg-[hsl(var(--slate-200))] shadow-[inset_0_1px_2px_rgb(15_23_42_/_0.06)]">
          {/* 已填充部分 */}
          <div
            className="absolute h-full rounded-full bg-gradient-to-r from-[hsl(var(--brand-500))] to-[hsl(var(--brand-600))] transition-[width] duration-150 ease-[cubic-bezier(0.25,1,0.5,1)]"
            style={{ width: `${percentage}%` }}
          />
        </div>
        <input
          {...inputProps}
          ref={ref}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value[0]}
          onChange={handleChange}
          disabled={disabled}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
        />
        {/* 拖把 */}
        <div
          className={cn(
            "absolute h-4 w-4 rounded-full border-2 border-[hsl(var(--brand-500))] bg-white shadow-soft pointer-events-none",
            "transition-[transform,box-shadow] duration-150 ease-[cubic-bezier(0.25,1,0.5,1)]",
            "group-hover:scale-110 group-hover:shadow-ring",
            "group-active:scale-125"
          )}
          style={{ left: `calc(${percentage}% - 8px)` }}
        />
      </div>
    )
  }
)
Slider.displayName = "Slider"

export { Slider }
