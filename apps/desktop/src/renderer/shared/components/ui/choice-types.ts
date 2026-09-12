import type { Ref } from 'react'
export type ChoiceOption = { value: string; label: string; description?: string; keywords?: readonly string[]; disabled?: boolean }
export type ChoiceProps = {
  id?: string; name?: string; value: string | null; onValueChange(value: string | null): void; onBlur?: () => void
  options: readonly ChoiceOption[]; placeholder?: string; size?: 'sm' | 'md'; disabled?: boolean; readOnly?: boolean
  loading?: boolean; errorMessage?: string; onRetry?: () => void; className?: string
  'aria-label'?: string; 'aria-labelledby'?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean
}
export type ComboboxProps = ChoiceProps & { ref?: Ref<HTMLInputElement> }
export type AutocompleteProps = Omit<ComboboxProps, 'value' | 'onValueChange'> & { value: string; onValueChange(value: string): void; onOptionSelect?(option: ChoiceOption): void }
export const encodeValue = (value: string | null): string => value === null ? '' : `v:${value}`
export const decodeValue = (value: string): string | null => value === '' ? null : value.slice(2)

export function withCurrentOption(options: readonly ChoiceOption[], value: string | null): readonly ChoiceOption[] {
  return value !== null && !options.some(option => option.value === value)
    ? [{ value, label: value, description: '当前选项不可用', disabled: true }, ...options] : options
}
export const optionMatches = (option: ChoiceOption, query: string) =>
  [option.label, option.value, ...(option.keywords ?? [])].some(text => text.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))
