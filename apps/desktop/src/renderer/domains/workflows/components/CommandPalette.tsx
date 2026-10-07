import { useEffect, useId, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { Dialog, DialogContent, DialogTitle } from './controls/dialog'
import { cn } from '../lib/utils'
import { filterCommands, type StudioCommand } from '../lib/studioCommands'

interface CommandPaletteProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  commands: StudioCommand[]
}

const firstEnabled = (list: StudioCommand[], from: number, step: 1 | -1): number => {
  for (let i = 0; i < list.length; i++) {
    const index = (from + step * i + list.length * 2) % list.length
    if (!list[index].disabled) return index
  }
  return -1
}

export function CommandPalette({ open, onOpenChange, commands }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const baseId = useId()
  const listId = `${baseId}-list`
  const optionId = (id: string) => `${baseId}-opt-${id}`
  const filtered = useMemo(() => filterCommands(commands, query), [commands, query])

  useEffect(() => { if (!open) setQuery('') }, [open])
  useEffect(() => { setActive(firstEnabled(filtered, 0, 1)) }, [filtered.length, query, open])

  const run = (command: StudioCommand | undefined) => {
    if (!command || command.disabled) return
    onOpenChange(false)
    command.run()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.nativeEvent.isComposing) return
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const step = e.key === 'ArrowDown' ? 1 : -1
      setActive(firstEnabled(filtered, active < 0 ? 0 : active + step, step))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      run(filtered[active])
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[20%] max-w-lg translate-y-0 gap-0 overflow-hidden p-0">
        <DialogTitle className="sr-only">命令面板</DialogTitle>
        <div className="flex items-center gap-2 border-b border-[hsl(var(--border))] px-3 py-2.5 pr-12">
          <Search className="h-4 w-4 flex-shrink-0 text-[hsl(var(--muted-foreground))]" aria-hidden />
          <input
            autoFocus
            role="combobox"
            aria-label="搜索命令"
            aria-expanded
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={filtered[active] ? optionId(filtered[active].id) : undefined}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="输入命令名称，例如：保存、导出"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[hsl(var(--muted-foreground))]"
          />
        </div>
        <ul id={listId} role="listbox" aria-label="命令" className="max-h-80 overflow-y-auto p-1">
          {filtered.map((c, i) => (
            <li
              key={c.id}
              id={optionId(c.id)}
              role="option"
              aria-selected={i === active}
              aria-disabled={c.disabled || undefined}
              onMouseMove={() => { if (!c.disabled && i !== active) setActive(i) }}
              onClick={() => run(c)}
              className={cn(
                'flex cursor-pointer items-center justify-between rounded-control px-3 py-2 text-sm',
                i === active && 'bg-[hsl(var(--accent))] ring-2 ring-inset ring-[hsl(var(--ring))]',
                c.disabled && 'cursor-not-allowed text-[hsl(var(--muted-foreground))] opacity-60',
              )}
            >
              <span>{c.label}</span>
              {c.shortcut && <kbd aria-hidden className="text-xs text-[hsl(var(--muted-foreground))]">{c.shortcut}</kbd>}
            </li>
          ))}
          {filtered.length === 0 && <li role="presentation" className="px-3 py-6 text-center text-sm text-[hsl(var(--muted-foreground))]">没有匹配的命令</li>}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
