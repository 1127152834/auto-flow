import { useId, useMemo, type Ref } from 'react'
import { Combobox } from '../components/ui/combobox'
import type { LabOption } from './fixtures'

type Props = { label: string; value: string | null; options: LabOption[]; onValueChange(value: string | null): void; inputRef?: Ref<HTMLInputElement>; onBlur?: () => void; error?: string }
// Fixture adapter only: every interaction is now exercised through the shared component.
export function LabCombobox({ label, value, options, onValueChange, inputRef, onBlur, error }: Props) {
  const id = useId()
  const choices = useMemo(() => options.map(option => ({ value: option.id, label: option.label })), [options])
  return <div className="grid min-w-0 gap-2"><label htmlFor={id} className="text-sm font-medium">{label}</label>
    <Combobox id={id} aria-label={label} ref={inputRef} value={value} options={choices} onValueChange={onValueChange} onBlur={onBlur} errorMessage={error} />
  </div>
}
