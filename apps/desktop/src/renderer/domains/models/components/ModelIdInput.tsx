import type { ModelDiscoveryRead } from '../model'
import { Autocomplete } from '../../../shared/components/ui/combobox'
import type { FieldA11y } from '../../../shared/components/FormField'

type RemoteModel = ModelDiscoveryRead['items'][number]
type Props = Partial<FieldA11y> & {
  value: string
  options: RemoteModel[]
  onChange(value: string, option?: RemoteModel): void
}

export function ModelIdInput({ value, options, onChange, ...a11y }: Props) {
  return <div onKeyDownCapture={event => {
    // Let an open suggestion list commit its option, including its metadata.
    // A free ID can be confirmed without submitting the surrounding form.
    if (event.key === 'Enter' && !event.nativeEvent.isComposing &&
      (event.target as HTMLElement).getAttribute('aria-expanded') !== 'true') {
      event.preventDefault()
      onChange(value.trim())
    }
  }}>
    <Autocomplete {...a11y} aria-label="模型标识" value={value}
      onValueChange={next => onChange(next)}
      onOptionSelect={option => onChange(option.value, options.find(item => item.modelKey === option.value))}
      options={options.map(option => ({
        value: option.modelKey,
        label: option.displayName === option.modelKey ? option.modelKey : `${option.displayName} · ${option.modelKey}`,
      }))}
      placeholder="搜索或输入模型标识" />
  </div>
}
