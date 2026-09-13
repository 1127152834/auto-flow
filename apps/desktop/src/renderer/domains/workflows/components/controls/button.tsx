// Source: WebRPA@5ccb900e, components/ui/button.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import { cn } from '../../lib/utils'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:
    | 'default'        // 主品牌（深蓝填充） - 主要操作
    | 'destructive'    // 危险红填充 - 删除/停止
    | 'success'        // 成功绿填充 - 运行/确认/上传
    | 'warning'        // 警告橙填充
    | 'info'           // 信息青蓝填充
    | 'outline'        // 蓝边线（描边主操作）
    | 'secondary'      // 中性灰底
    | 'ghost'          // 弱品牌底（图标按钮专用）
    | 'subtle'         // 中性低调
    | 'link'           // 文字链接
    | 'tonal'          // 蓝弱调（次级）
    | 'tonal-success'
    | 'tonal-warning'
    | 'tonal-danger'
    | 'tonal-info'
  size?: 'default' | 'sm' | 'lg' | 'icon' | 'xs' | 'icon-sm'
  /** 兼容旧调用：禁用动效（占位参数） */
  noMotion?: boolean
  /** 显示加载态 */
  loading?: boolean
}

/**
 * 设计原则：
 * - 蓝白主调，按钮按功能着色
 * - 实心按钮：彩色填充 + 阴影 + 悬浮微抬升
 * - tonal 变体：浅彩底 + 深彩字 + 半透明边
 * - 所有按钮均带 active 微下沉、focus 蓝光环
 * - 过渡 140ms cubic-bezier(0.25, 1, 0.5, 1) - 丝滑、克制
 */
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', noMotion: _noMotion, loading, children, disabled, ...props }, ref) => {
    const base =
      'group relative inline-flex items-center justify-center gap-1.5 whitespace-nowrap ' +
      'rounded-[7px] text-[13px] font-medium select-none ' +
      'transition-[background-color,border-color,color,box-shadow,transform,filter] ' +
      'duration-150 ease-[cubic-bezier(0.25,1,0.5,1)] ' +
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] focus-visible:ring-offset-1 focus-visible:ring-offset-[hsl(var(--background))] ' +
      'disabled:pointer-events-none disabled:opacity-50 ' +
      'active:translate-y-[1px] active:scale-[0.99]'

    const variants: Record<NonNullable<ButtonProps['variant']>, string> = {
      // 主品牌深蓝
      default:
        '!bg-[hsl(var(--brand-600))] !text-white !border-transparent shadow-soft ' +
        'hover:!bg-[hsl(var(--brand-700))] hover:shadow-brand-glow hover:-translate-y-[1px] ' +
        'active:!bg-[hsl(var(--brand-800))]',
      // 危险红
      destructive:
        '!bg-[hsl(var(--danger-500))] !text-white !border-transparent shadow-soft ' +
        'hover:!bg-[hsl(var(--danger-600))] hover:shadow-danger-glow hover:-translate-y-[1px] ' +
        'active:!bg-[hsl(var(--danger-700))]',
      // 成功绿
      success:
        '!bg-[hsl(var(--success-600))] !text-white !border-transparent shadow-soft ' +
        'hover:!bg-[hsl(var(--success-700))] hover:shadow-success-glow hover:-translate-y-[1px] ' +
        'active:brightness-95',
      // 警告橙
      warning:
        '!bg-[hsl(var(--warning-500))] !text-white !border-transparent shadow-soft ' +
        'hover:!bg-[hsl(var(--warning-600))] hover:shadow-warning-glow hover:-translate-y-[1px] ' +
        'active:!bg-[hsl(var(--warning-700))]',
      // 信息青蓝
      info:
        '!bg-[hsl(var(--info-500))] !text-white !border-transparent shadow-soft ' +
        'hover:!bg-[hsl(var(--info-600))] hover:shadow-pop hover:-translate-y-[1px] ' +
        'active:!bg-[hsl(var(--info-700))]',
      // 描边（蓝弱底 + 蓝字 + 蓝边）
      outline:
        'bg-[hsl(var(--brand-50))] text-[hsl(var(--brand-700))] ' +
        'border border-[hsl(var(--brand-500)/0.35)] shadow-xs ' +
        'hover:bg-[hsl(var(--brand-100))] hover:border-[hsl(var(--brand-500)/0.6)] hover:text-[hsl(var(--brand-800))] hover:shadow-soft ' +
        'active:bg-[hsl(var(--brand-200))]',
      // 中性次级
      secondary:
        'bg-[hsl(var(--slate-100))] text-[hsl(var(--slate-700))] ' +
        'border border-[hsl(var(--slate-200))] ' +
        'hover:bg-[hsl(var(--slate-200))] hover:border-[hsl(var(--slate-300))] hover:text-[hsl(var(--slate-900))]',
      // ghost：用于图标按钮，悬浮才显形（仍带可见兜底）
      ghost:
        'bg-transparent text-[hsl(var(--slate-600))] ' +
        'hover:bg-[hsl(var(--brand-50))] hover:text-[hsl(var(--brand-700))] ' +
        'active:bg-[hsl(var(--brand-100))]',
      // 极弱中性
      subtle:
        'bg-[hsl(var(--slate-100))] text-[hsl(var(--muted-foreground))] ' +
        'border border-[hsl(var(--slate-200))] ' +
        'hover:bg-[hsl(var(--slate-200))] hover:text-[hsl(var(--foreground))]',
      link:
        'text-[hsl(var(--brand-600))] underline-offset-4 hover:underline hover:text-[hsl(var(--brand-700))] px-0 h-auto',
      // 弱调系列（次要操作）
      tonal:
        'bg-[hsl(var(--brand-50))] text-[hsl(var(--brand-700))] ' +
        'border border-[hsl(var(--brand-500)/0.25)] ' +
        'hover:bg-[hsl(var(--brand-100))] hover:border-[hsl(var(--brand-500)/0.45)]',
      'tonal-success':
        'bg-[hsl(var(--success-50))] text-[hsl(var(--success-700))] ' +
        'border border-[hsl(var(--success-500)/0.3)] ' +
        'hover:bg-[hsl(var(--success-100))] hover:border-[hsl(var(--success-500)/0.5)]',
      'tonal-warning':
        'bg-[hsl(var(--warning-50))] text-[hsl(var(--warning-700))] ' +
        'border border-[hsl(var(--warning-500)/0.3)] ' +
        'hover:bg-[hsl(var(--warning-100))] hover:border-[hsl(var(--warning-500)/0.5)]',
      'tonal-danger':
        'bg-[hsl(var(--danger-50))] text-[hsl(var(--danger-700))] ' +
        'border border-[hsl(var(--danger-500)/0.3)] ' +
        'hover:bg-[hsl(var(--danger-100))] hover:border-[hsl(var(--danger-500)/0.5)]',
      'tonal-info':
        'bg-[hsl(var(--info-50))] text-[hsl(var(--info-700))] ' +
        'border border-[hsl(var(--info-500)/0.3)] ' +
        'hover:bg-[hsl(var(--info-100))] hover:border-[hsl(var(--info-500)/0.5)]',
    }

    const sizes: Record<NonNullable<ButtonProps['size']>, string> = {
      xs: 'h-6 px-2 text-[11px] gap-1 rounded-[5px]',
      sm: 'h-7 px-2.5 text-[12px] rounded-[6px]',
      default: 'h-8 px-3.5',
      lg: 'h-10 px-5 text-[14px] rounded-[8px]',
      icon: 'h-8 w-8 p-0',
      'icon-sm': 'h-7 w-7 p-0 rounded-[6px]',
    }

    // ghost + icon 增强：默认就有微弱底，悬浮明显
    const ghostIconBoost =
      variant === 'ghost' && (size === 'icon' || size === 'icon-sm')
        ? 'bg-[hsl(var(--slate-100))] hover:bg-[hsl(var(--brand-50))] text-[hsl(var(--slate-600))] hover:text-[hsl(var(--brand-700))] border border-transparent hover:border-[hsl(var(--brand-500)/0.3)]'
        : ''

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(base, variants[variant], sizes[size], ghostIconBoost, className)}
        {...props}
      >
        {loading && (
          <span
            className={cn(
              'inline-block rounded-full border-2 border-current border-t-transparent animate-spin-smooth',
              size === 'xs' || size === 'sm' ? 'w-3 h-3 border-[1.5px]' : 'w-3.5 h-3.5'
            )}
            aria-hidden="true"
          />
        )}
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'

export { Button }
