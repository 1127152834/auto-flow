import { useLayoutEffect, useState, type CSSProperties } from 'react'
import { CalendarBlank } from '@phosphor-icons/react'
import { DayPicker } from '@daypicker/react'
import { zhCN } from '@daypicker/react/locale'
import '@daypicker/react/style.css'
import './calendar-date-input.css'
import { Input } from './input'
import { IconButton } from './icon-button'
import { Popover, PopoverContent, PopoverTrigger } from './popover'

type Props = {
  id?: string; value: string; onValueChange(value: string): void
  disabled?: boolean; readOnly?: boolean
  'aria-label'?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean | 'true' | 'false'
}

// Local calendar days are not instants. Never round-trip through UTC or normalize invalid drafts.
function calendarDay(value: string): Date | undefined {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return undefined
  const [, year, month, day] = match.map(Number)
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > 31) return undefined
  const date = new Date(); date.setHours(12, 0, 0, 0); date.setFullYear(year, month - 1, day)
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : undefined
}

export function CalendarDateInput({ value, onValueChange, disabled, readOnly, ...inputProps }: Props) {
  const [open, setOpen] = useState(false)
  const selected = calendarDay(value)
  const label = inputProps['aria-label'] ?? '日期'
  const locked = disabled || readOnly
  useLayoutEffect(() => { if (locked) setOpen(false) }, [locked])
  return <div className="relative min-w-0">
    <Input {...inputProps} type="text" value={value} disabled={disabled} readOnly={readOnly}
      className="h-12 pr-12 text-base" onChange={event => onValueChange(event.target.value)} />
    <Popover open={open && !locked} onOpenChange={next => setOpen(next && !locked)}>
      <PopoverTrigger asChild><IconButton aria-label={`选择${label}`} disabled={locked} variant="ghost"
        className="absolute right-1 top-1 h-10 w-10" ><CalendarBlank size={21} /></IconButton></PopoverTrigger>
      <PopoverContent aria-label={`${label}日历`} className="w-auto p-3" align="end" onOpenAutoFocus={event => event.preventDefault()}>
        <DayPicker mode="single" locale={zhCN} selected={selected} defaultMonth={selected} autoFocus
          className="af-calendar" style={{ '--rdp-accent-color': 'var(--color-clay)', '--rdp-accent-background-color': 'var(--color-clay-soft)' } as CSSProperties}
          onSelect={day => {
            if (!day || locked) return
            onValueChange(`${String(day.getFullYear()).padStart(4, '0')}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`)
            setOpen(false)
          }} />
      </PopoverContent>
    </Popover>
  </div>
}
