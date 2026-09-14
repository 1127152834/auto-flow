import { MagnifyingGlass, X } from '@phosphor-icons/react'
import { useImperativeHandle, useRef } from 'react'
import { Input, type InputProps } from './input'
import { IconButton } from './icon-button'
import { Spinner } from './spinner'
import { cn } from '../../lib/utils'

type SearchInputProps = Omit<InputProps, 'type' | 'value' | 'defaultValue'> & {
  value: string
  onClear?: () => void
  clearLabel?: string
  loading?: boolean
  leadingIcon?: boolean
}
export function SearchInput({ ref, onClear, clearLabel = '清除搜索', loading, leadingIcon = true, size, className, ...props }: SearchInputProps) {
  const input = useRef<HTMLInputElement>(null)
  useImperativeHandle(ref, () => input.current!)
  const canClear = Boolean(onClear && props.value && !props.readOnly && !props.disabled)
  return <div className="relative min-w-0">
    {leadingIcon ? <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted">{loading ? <Spinner /> : <MagnifyingGlass size={16} aria-hidden />}</span> : null}
    <Input {...props} ref={input} size={size} type="search" aria-busy={loading || props['aria-busy']} className={cn(leadingIcon ? 'pl-10 pr-10' : 'pl-3 pr-10', className)} />
    {canClear ? <span className="absolute inset-y-0 right-1 flex items-center"><IconButton aria-label={clearLabel} size="sm" variant="ghost" onClick={() => { onClear?.(); input.current?.focus() }}><X size={14} /></IconButton></span> : null}
  </div>
}
