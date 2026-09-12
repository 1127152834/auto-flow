import { CaretDown, Check, X } from '@phosphor-icons/react'
import { Button as AriaButton, ComboBox, Input, ListBox, ListBoxItem, Popover, Virtualizer, ListLayout } from 'react-aria-components'
import { useId, useEffect, useState, useMemo, useRef, useImperativeHandle } from 'react'
import { cn } from '../../lib/utils'
import { useOverlayHost } from './overlay-host'
import { type AutocompleteProps, type ComboboxProps, type ChoiceOption, encodeValue, decodeValue, optionMatches, withCurrentOption } from './choice-types'
import { IconButton } from './icon-button'
import { Button } from './button'
import { Spinner } from './spinner'

export function Combobox(props: ComboboxProps) { return <ChoiceInput {...props} mode="strict" /> }
export function Autocomplete(props: AutocompleteProps) { return <ChoiceInput {...props} mode="free" /> }
type Props = (ComboboxProps & { mode: 'strict' }) | (AutocompleteProps & { mode: 'free' })
function ChoiceInput(props: Props) {
  const { mode, value, options, onBlur, ref, id, name, size = 'md', disabled, readOnly, loading, errorMessage, onRetry, className, placeholder = '搜索或选择' } = props
  const host = useOverlayHost(), errorId = useId(), localRef = useRef<HTMLInputElement>(null), composing = useRef(false)
  useImperativeHandle(ref, () => localRef.current!)
  const label = options.find(option => option.value === value)?.label ?? value ?? ''
  const [query, setQuery] = useState(label)
  // Only actual text edits enable automatic opening; restored labels must stay closed.
  const [menuTrigger, setMenuTrigger] = useState<'manual' | 'input'>('manual')
  useEffect(() => { if (mode === 'strict') { setQuery(label); setMenuTrigger('manual') } }, [label, value, mode])
  const inputValue = mode === 'free' ? value : query
  const items = useMemo(() => (mode === 'strict' ? withCurrentOption(options, value) : options).filter(option => optionMatches(option, inputValue ?? '')), [options, value, inputValue, mode])
  const [showAll, setShowAll] = useState(false)
  const selected = mode === 'free' ? options.find(option => option.value === value)?.value ?? null : value
  const unavailable = mode === 'strict' && value !== null && !options.some(option => option.value === value)
  const unavailableId = useId()
  const description = [props['aria-describedby'], errorMessage ? errorId : undefined, unavailable ? unavailableId : undefined].filter(Boolean).join(' ') || undefined
  const restore = () => { setMenuTrigger('manual'); if (mode === 'strict') setQuery(label) }
  const listbox = (
        <ListBox<ChoiceOption> className="min-h-0 max-h-80 overflow-auto overscroll-contain outline-none" renderEmptyState={() => <p className="p-3 text-sm text-muted">{loading ? '正在加载选项…' : '没有匹配项'}</p>}>
          {option => <ListBoxItem data-choice-value={option.value} id={encodeValue(option.value)} textValue={mode === 'free' ? option.value : option.label} isDisabled={option.disabled} className="af-choice-option">
            {({ isSelected }) => <><span className="min-w-0 flex-1 break-words">{option.label}{option.description ? <span className="block text-xs text-muted">{option.description}</span> : null}</span><Check aria-hidden size={16} className={isSelected ? 'shrink-0 text-clay' : 'invisible shrink-0'} /></>}
          </ListBoxItem>}
        </ListBox>
  )
  return <div className={cn('grid min-w-0 gap-2', className)}>
    <ComboBox<ChoiceOption> menuTrigger={menuTrigger} aria-label={props['aria-label']} aria-labelledby={props['aria-labelledby']}
      value={selected === null ? null : encodeValue(selected)} inputValue={inputValue ?? ''} items={showAll ? (mode === 'strict' ? withCurrentOption(options, value) : options) : items}
      onInputChange={text => { setMenuTrigger('input'); setShowAll(false); if (props.mode === 'free') props.onValueChange(text); else setQuery(text) }}
      onChange={key => {
        if (key === null) return
        const option = options.find(item => item.value === decodeValue(String(key)))
        if (!option || option.disabled) return
        setMenuTrigger('manual')
        if (props.mode === 'free') { props.onValueChange(option.value); props.onOptionSelect?.(option) }
        else { setQuery(option.label); if (option.value !== value) props.onValueChange(option.value) }
      }}
      allowsCustomValue={mode === 'free'} allowsEmptyCollection isDisabled={disabled} isReadOnly={readOnly} isInvalid={props['aria-invalid'] || Boolean(errorMessage)} validationBehavior="aria"
      onOpenChange={(next, trigger) => { setShowAll(next && trigger === 'manual'); if (!next) restore() }} className="min-w-0">
      <div className="flex min-w-0 items-center gap-1">
        <Input data-choice-value={value ?? undefined} ref={localRef} id={id} aria-describedby={description} aria-busy={loading || undefined} data-af-control placeholder={placeholder}
          onBlur={() => { restore(); onBlur?.() }} onCompositionStart={() => { composing.current = true }} onCompositionEnd={() => { composing.current = false }}
          onKeyDownCapture={event => { if (event.key === 'Enter' && (composing.current || event.nativeEvent.isComposing)) { event.preventDefault(); event.stopPropagation() } }}
          className={cn('min-w-0 flex-1 px-3', size === 'sm' ? 'h-[var(--control-sm)] text-xs' : 'h-[var(--control-md)] text-sm')} />
        <AriaButton aria-label={`展开 ${props['aria-label'] ?? ''}`.trim()} className={cn('af-choice-trigger grid shrink-0 place-items-center rounded-control border border-control-border bg-surface text-ink', size === 'sm' ? 'h-8 w-8' : 'h-10 w-10')}>
          {loading ? <Spinner size={16} /> : <CaretDown size={16} aria-hidden />}
        </AriaButton>
        {(mode === 'strict' ? value !== null : value !== '') && !disabled && !readOnly ? <IconButton aria-label="清除选择" variant="ghost" size={size} onMouseDown={event => event.preventDefault()} onClick={() => { setMenuTrigger('manual'); if (props.mode === 'free') props.onValueChange(''); else props.onValueChange(null); setQuery(''); localRef.current?.focus() }}><X size={14} /></IconButton> : null}
      </div>
      <Popover data-af-popup UNSTABLE_portalContainer={host.container} style={host.style} offset={6} maxHeight={320}
        className="af-choice-popup max-w-[min(36rem,90vw)] min-w-[min(20rem,80vw)] w-[var(--trigger-width)] flex flex-col overflow-hidden p-1">
        {options.length > 100 ? <Virtualizer layout={ListLayout} layoutOptions={{ estimatedRowSize: 40 }} shouldObserveItemSize>{listbox}</Virtualizer> : listbox}
      </Popover>
    </ComboBox>
    {name && value !== null ? <input type="hidden" name={name} value={value} disabled={disabled} /> : null}
    {unavailable ? <p id={unavailableId} className="text-xs text-muted">当前选项不可用，请重新选择</p> : null}
    {loading ? <p role="status" className="text-xs text-muted">正在加载选项…</p> : null}
    {errorMessage ? <div className="flex items-center gap-2"><p role="alert" id={errorId} className="text-xs text-danger">{errorMessage}</p>{onRetry ? <Button size="sm" onClick={onRetry} disabled={loading}>重试加载</Button> : null}</div> : null}
  </div>
}
