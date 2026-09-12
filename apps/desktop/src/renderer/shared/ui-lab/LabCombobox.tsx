import { CaretDown, Check } from '@phosphor-icons/react'
import { Button, ComboBox, Input, Label, ListBox, ListBoxItem, Popover } from 'react-aria-components'
import { useId, type Ref } from 'react'
import { useOverlayHost } from '../components/ui/overlay-host'
import type { LabOption } from './fixtures'

type Props = {
  label: string
  value: string | null
  options: LabOption[]
  onValueChange(value: string | null): void
  inputRef?: Ref<HTMLInputElement>
  onBlur?: () => void
  error?: string
}

// G0's integration probe only. The domain-facing choice API is implemented in T5.
export function LabCombobox({ label, value, options, onValueChange, inputRef, onBlur, error }: Props) {
  const host = useOverlayHost()
  const errorId = useId()
  return <ComboBox<LabOption> value={value} onChange={key => onValueChange(key === null ? null : String(key))}
    defaultItems={options} isInvalid={Boolean(error)} validationBehavior="aria" allowsEmptyCollection className="grid min-w-0 gap-2">
    <Label className="text-sm font-medium">{label}</Label>
    <div className="flex min-w-0 items-center gap-2">
      <Input aria-describedby={error ? errorId : undefined} ref={inputRef} onBlur={onBlur} data-af-control className="h-10 min-w-0 flex-1 px-3 text-sm" placeholder="搜索或展开完整目录" />
      <Button aria-label="展开" className="grid h-10 w-10 shrink-0 place-items-center rounded-control border border-control-border bg-surface hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-clay"><CaretDown size={18} aria-hidden /></Button>
    </div>
    {error ? <p id={errorId} role="alert" className="text-xs text-danger">{error}</p> : null}
    <Popover data-af-popup UNSTABLE_portalContainer={host.container} style={host.style} offset={8} maxHeight={320}
      className="w-[var(--trigger-width)] min-w-[min(20rem,80vw)] max-w-[min(36rem,85vw)] overflow-y-auto overscroll-contain rounded-control border border-control-border bg-surface p-1 shadow-popup">
      <ListBox<LabOption> className="p-1 outline-none" renderEmptyState={() => <p className="p-3 text-sm text-muted">没有匹配项</p>}>
        {item => <ListBoxItem id={item.id} textValue={item.label} className="flex cursor-default items-start gap-2 rounded-control px-3 py-2 text-sm outline-none data-[focused]:bg-surface-hover data-[selected]:bg-clay-soft">
          {({ isSelected }) => <><span className="min-w-0 flex-1 break-words">{item.label}</span><Check aria-hidden size={16} className={isSelected ? 'mt-0.5 shrink-0 text-clay' : 'invisible shrink-0'} /></>}
        </ListBoxItem>}
      </ListBox>
    </Popover>
  </ComboBox>
}
