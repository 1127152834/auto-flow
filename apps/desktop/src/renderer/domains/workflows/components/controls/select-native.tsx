// Source: WebRPA@5ccb900e, components/ui/select-native.tsx; see SOURCE.md for license and adaptation boundaries.
import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { ChevronDown, Check } from 'lucide-react'
import { cn } from '../../lib/utils'

/**
 * SelectNative - WebRPA 主题统一下拉框
 *
 * 对外 API 与原生 <select> 兼容：
 *   <SelectNative value={v} onChange={(e) => setV(e.target.value)}>
 *     <option value="a">A</option>
 *     <option value="b" disabled>B</option>
 *     <optgroup label="组1">
 *       <option value="c">C</option>
 *     </optgroup>
 *   </SelectNative>
 *
 * 实际由 Radix Select 渲染，完全 CSS 可控。
 */
export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'onChange' | 'size'> {
  /**
   * 兼容原生 onChange API。会接收一个简化的合成事件对象 { target: { value } }。
   * 类型上同时兼容 React.ChangeEventHandler<HTMLSelectElement> 的常见用法（取 e.target.value）。
   */
  onChange?: (event: any) => void
  /** 当未选中任何值时显示的占位文本 */
  placeholder?: string
}

interface ParsedOption {
  value: string
  label: React.ReactNode
  disabled?: boolean
  group?: string
}

// Radix Select 不允许 Item 的 value 为空字符串，用哨兵值在内部替代，
// 对外 API 仍然保持空字符串语义。
const EMPTY_SENTINEL = '__webrpa_empty__'

function flattenOptions(children: React.ReactNode): ParsedOption[] {
  const out: ParsedOption[] = []
  React.Children.forEach(children, (node) => {
    if (!React.isValidElement(node)) return
    const props: any = node.props
    if (node.type === 'option') {
      out.push({
        value: String(props.value ?? ''),
        label: props.children ?? String(props.value ?? ''),
        disabled: !!props.disabled,
      })
    } else if (node.type === 'optgroup') {
      const groupLabel = String(props.label ?? '')
      React.Children.forEach(props.children, (child) => {
        if (!React.isValidElement(child) || child.type !== 'option') return
        const cp: any = child.props
        out.push({
          value: String(cp.value ?? ''),
          label: cp.children ?? String(cp.value ?? ''),
          disabled: !!cp.disabled,
          group: groupLabel,
        })
      })
    } else {
      // Fragment / 其它包装节点：递归解析其 children
      // 兼容 children 是数组、单个 node 或 undefined 三种形态
      if (props?.children !== undefined && props?.children !== null) {
        out.push(...flattenOptions(props.children))
      }
    }
  })
  return out
}

const SelectNative = React.forwardRef<HTMLButtonElement, SelectProps>(
  (
    {
      className,
      children,
      value,
      defaultValue,
      onChange,
      disabled,
      placeholder,
      id,
      name,
      title,
      ...rest
    },
    ref
  ) => {
    const options = React.useMemo(() => flattenOptions(children), [children])
    const [internal, setInternal] = React.useState<string | undefined>(
      value !== undefined ? String(value) : defaultValue !== undefined ? String(defaultValue) : undefined
    )

    React.useEffect(() => {
      if (value !== undefined) setInternal(String(value))
    }, [value])

    const isControlled = value !== undefined
    const current = isControlled ? String(value) : internal

    const handleChange = (next: string) => {
      // 把哨兵值还原成空字符串再对外暴露
      const realNext = next === EMPTY_SENTINEL ? '' : next
      if (!isControlled) setInternal(realNext)
      onChange?.({ target: { value: realNext } })
    }

    // 计算当前显示文本
    const currentOption = options.find((o) => o.value === current)
    const displayLabel = currentOption?.label ?? placeholder ?? ''

    // Radix 用的当前值：空字符串映射为哨兵值
    const radixCurrent = current === '' ? EMPTY_SENTINEL : current

    // 分组渲染
    const groups = React.useMemo(() => {
      const map = new Map<string, ParsedOption[]>()
      for (const opt of options) {
        const key = opt.group || ''
        if (!map.has(key)) map.set(key, [])
        map.get(key)!.push(opt)
      }
      return Array.from(map.entries())
    }, [options])

    return (
      <SelectPrimitive.Root
        value={radixCurrent}
        onValueChange={handleChange}
        disabled={disabled}
      >
        <SelectPrimitive.Trigger
          ref={ref}
          id={id}
          name={name}
          title={title}
          className={cn(
            // 形态
            'group relative flex h-8 w-full items-center justify-between gap-2 rounded-[6px]',
            'border border-[hsl(var(--slate-200))] bg-[hsl(var(--slate-50))]',
            'px-2.5 py-1 pr-2 text-[13px] text-[hsl(var(--foreground))]',
            'shadow-[inset_0_1px_2px_rgb(15_23_42_/_0.04)]',
            'transition-[border-color,background-color,box-shadow,transform] duration-150 ease-[cubic-bezier(0.25,1,0.5,1)]',
            // 交互
            'hover:border-[hsl(var(--slate-300))] hover:bg-[hsl(var(--card))]',
            'data-[state=open]:border-[hsl(var(--brand-500))] data-[state=open]:bg-[hsl(var(--card))] data-[state=open]:ring-2 data-[state=open]:ring-[hsl(var(--brand-500)/0.18)]',
            'focus-visible:outline-none focus-visible:border-[hsl(var(--brand-500))] focus-visible:bg-[hsl(var(--card))] focus-visible:ring-2 focus-visible:ring-[hsl(var(--brand-500)/0.18)]',
            'disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer text-left',
            className
          )}
          {...(rest as any)}
        >
          <span className="flex-1 truncate">
            {currentOption ? (
              <SelectPrimitive.Value>{displayLabel as any}</SelectPrimitive.Value>
            ) : (
              <span className="text-[hsl(var(--muted-foreground))]">{placeholder || '请选择'}</span>
            )}
          </span>
          <SelectPrimitive.Icon asChild>
            <ChevronDown className="h-3.5 w-3.5 text-[hsl(var(--muted-foreground))] transition-transform duration-150 group-data-[state=open]:rotate-180 group-data-[state=open]:text-[hsl(var(--brand-600))]" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>

        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            position="popper"
            sideOffset={6}
            style={{ zIndex: 2147483647 }}
            className={cn(
              'min-w-[var(--radix-select-trigger-width)] max-h-[min(360px,var(--radix-select-content-available-height))]',
              'overflow-hidden rounded-[10px] border border-[hsl(var(--border))] bg-[hsl(var(--card))]',
              'shadow-pop-xl ring-1 ring-[hsl(var(--brand-500)/0.06)]',
              'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
              'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
              'data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2'
            )}
          >
            <SelectPrimitive.ScrollUpButton className="flex h-6 cursor-default items-center justify-center bg-[hsl(var(--card))] text-[hsl(var(--muted-foreground))]">
              <ChevronDown className="h-3.5 w-3.5 rotate-180" />
            </SelectPrimitive.ScrollUpButton>

            <SelectPrimitive.Viewport className="p-1">
              {groups.map(([groupName, opts], gi) => (
                <React.Fragment key={`g-${gi}-${groupName}`}>
                  {groupName && (
                    <div className="px-2 pt-1.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[hsl(var(--muted-foreground))]">
                      {groupName}
                    </div>
                  )}
                  {opts.map((opt) => (
                    <SelectPrimitive.Item
                      key={opt.value}
                      value={opt.value === '' ? EMPTY_SENTINEL : opt.value}
                      disabled={opt.disabled}
                      className={cn(
                        'relative flex select-none items-center gap-2 rounded-[6px] py-1.5 pl-7 pr-2.5',
                        'text-[13px] leading-tight text-[hsl(var(--slate-700))]',
                        'cursor-pointer outline-none transition-colors duration-100',
                        'hover:bg-[hsl(var(--brand-50))] hover:text-[hsl(var(--brand-700))]',
                        'data-[highlighted]:bg-[hsl(var(--brand-50))] data-[highlighted]:text-[hsl(var(--brand-700))]',
                        'data-[state=checked]:bg-[hsl(var(--brand-50))] data-[state=checked]:text-[hsl(var(--brand-700))] data-[state=checked]:font-semibold',
                        'data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 data-[disabled]:hover:bg-transparent data-[disabled]:hover:text-[hsl(var(--slate-700))]'
                      )}
                    >
                      <span className="absolute left-1.5 flex h-3.5 w-3.5 items-center justify-center">
                        <SelectPrimitive.ItemIndicator>
                          <Check className="h-3.5 w-3.5 text-[hsl(var(--brand-600))]" strokeWidth={2.6} />
                        </SelectPrimitive.ItemIndicator>
                      </span>
                      <SelectPrimitive.ItemText>{opt.label}</SelectPrimitive.ItemText>
                    </SelectPrimitive.Item>
                  ))}
                  {gi < groups.length - 1 && (
                    <div className="my-1 h-px bg-[hsl(var(--border))] mx-1" />
                  )}
                </React.Fragment>
              ))}
            </SelectPrimitive.Viewport>

            <SelectPrimitive.ScrollDownButton className="flex h-6 cursor-default items-center justify-center bg-[hsl(var(--card))] text-[hsl(var(--muted-foreground))]">
              <ChevronDown className="h-3.5 w-3.5" />
            </SelectPrimitive.ScrollDownButton>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>
    )
  }
)
SelectNative.displayName = 'SelectNative'

export { SelectNative }
