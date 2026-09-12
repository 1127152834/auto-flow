import { X } from '@phosphor-icons/react'
import type { InputHTMLAttributes } from 'react'
import { Input } from '../../../shared/components/ui/input'
import { Badge } from '../../../shared/components/ui/badge'
import { IconButton } from '../../../shared/components/ui/icon-button'

export function mergeModelTags(current: string[], input: string): string[] {
  return [...new Set([...current, ...input.split(/[,，]/).map(tag => tag.trim()).filter(Boolean)])]
}

type Props = Pick<InputHTMLAttributes<HTMLInputElement>, 'id' | 'aria-label' | 'aria-describedby' | 'aria-invalid' | 'disabled'> & {
  value: string[]
  draft: string
  onValueChange(value: string[]): void
  onDraftChange(draft: string): void
}

export function TagInput({ value, draft, onValueChange, onDraftChange, ...a11y }: Props) {
  const commit = () => {
    onValueChange(mergeModelTags(value, draft))
    onDraftChange('')
  }
  return <div className="flex flex-wrap items-center gap-2 rounded-control border border-control-border bg-surface p-2">
    {value.map(tag => <Badge key={tag} tone="neutral">
      {tag}
      <IconButton size="sm" variant="ghost" aria-label={`移除标签 ${tag}`} disabled={a11y.disabled}
        onClick={() => onValueChange(value.filter(item => item !== tag))}>
        <X size={12} aria-hidden />
      </IconButton>
    </Badge>)}
    <Input {...a11y} className="min-w-32 flex-1" value={draft}
      onChange={event => onDraftChange(event.target.value)}
      onKeyDown={event => {
        if (event.nativeEvent.isComposing) return
        if (['Enter', ',', '，'].includes(event.key)) {
          event.preventDefault()
          commit()
        }
      }}
      onBlur={commit} placeholder="输入后按回车添加" />
  </div>
}
