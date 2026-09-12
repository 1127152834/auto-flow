import * as SelectPrimitive from '@radix-ui/react-select'
import { CaretDown, CaretUp, Check, X } from '@phosphor-icons/react'
import { useId, useState, useRef, useImperativeHandle, type Ref } from 'react'
import { cn } from '../../lib/utils'
import { useOverlayHost } from './overlay-host'
import { type ChoiceProps, encodeValue, decodeValue, withCurrentOption } from './choice-types'
import { IconButton } from './icon-button'
import { Button } from './button'
import { Spinner } from './spinner'

export function Select({ ref, value, options, onValueChange, onBlur, id, name, size = 'md', disabled, readOnly, loading, errorMessage, onRetry, className, placeholder = '请选择', ...aria }: ChoiceProps & { ref?: Ref<HTMLButtonElement> }) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  useImperativeHandle(ref, () => trigger.current!)
  const host = useOverlayHost(), errorId = useId()
  const items = withCurrentOption(options, value)
  const unavailable = value !== null && !options.some(option => option.value === value)
  const unavailableId = useId()
  const description = [aria['aria-describedby'], errorMessage ? errorId : undefined, unavailable ? unavailableId : undefined].filter(Boolean).join(' ') || undefined
  return <div className={cn('grid min-w-0 gap-2', className)}>
    <div className="flex min-w-0 items-center gap-1">
      <SelectPrimitive.Root value={encodeValue(value)} onValueChange={key => { if (!readOnly && !disabled) onValueChange(decodeValue(key)) }} disabled={disabled}
        open={open && !readOnly} onOpenChange={next => { if (!readOnly) setOpen(next) }}>
        <SelectPrimitive.Trigger {...aria} id={id} ref={trigger} onBlur={onBlur} aria-readonly={readOnly || undefined} aria-invalid={aria['aria-invalid'] || Boolean(errorMessage) || undefined} aria-describedby={description} aria-busy={loading || undefined}
          data-af-control className={cn('flex min-w-0 flex-1 items-center justify-between gap-2 px-3 text-left', size === 'sm' ? 'h-[var(--control-sm)] text-xs' : 'h-[var(--control-md)] text-sm', readOnly && 'select-text')}>
          <span className="min-w-0 flex-1 truncate"><SelectPrimitive.Value placeholder={placeholder}>{value === null ? placeholder : items.find(option => option.value === value)?.label}</SelectPrimitive.Value></span>
          <SelectPrimitive.Icon>{loading ? <Spinner size={16} /> : <CaretDown size={16} aria-hidden />}</SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectPrimitive.Portal container={host.container}>
          <SelectPrimitive.Content data-af-popup style={host.style} position="popper" sideOffset={6} collisionPadding={12} className="af-choice-popup min-w-[var(--radix-select-trigger-width)] max-w-[min(36rem,90vw)] overflow-hidden">
            <SelectPrimitive.ScrollUpButton className="flex h-6 items-center justify-center"><CaretUp size={14} aria-hidden /></SelectPrimitive.ScrollUpButton>
            <SelectPrimitive.Viewport className="af-select-viewport max-h-[min(20rem,var(--radix-select-content-available-height))] p-1">
              {items.map(option => <SelectPrimitive.Item key={option.value} value={encodeValue(option.value)} disabled={option.disabled} textValue={option.label} className="af-choice-option">
                <span className="min-w-0 flex-1"><SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>{option.description ? <span className="block text-xs text-muted">{option.description}</span> : null}</span>
                <SelectPrimitive.ItemIndicator><Check aria-hidden size={16} /></SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>)}
              {!items.length ? <p className="p-3 text-sm text-muted">暂无选项</p> : null}
            </SelectPrimitive.Viewport>
            <SelectPrimitive.ScrollDownButton className="flex h-6 items-center justify-center"><CaretDown size={14} aria-hidden /></SelectPrimitive.ScrollDownButton>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>
      {value !== null && !readOnly && !disabled ? <IconButton aria-label="清除选择" size={size} variant="ghost" onClick={() => { onValueChange(null); trigger.current?.focus() }}><X size={14} /></IconButton> : null}
    </div>
    {name && value !== null ? <input type="hidden" name={name} value={value} disabled={disabled} /> : null}
    {unavailable ? <p id={unavailableId} className="text-xs text-muted">当前选项不可用，请重新选择</p> : null}
    {loading ? <p role="status" className="text-xs text-muted">正在加载选项…</p> : null}
    {errorMessage ? <div className="flex items-center gap-2"><p role="alert" id={errorId} className="text-xs text-danger">{errorMessage}</p>{onRetry ? <Button size="sm" onClick={onRetry} disabled={loading}>重试加载</Button> : null}</div> : null}
  </div>
}
