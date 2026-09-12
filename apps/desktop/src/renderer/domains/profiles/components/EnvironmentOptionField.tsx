import { useEffect, useRef, useState } from 'react'
import { useController, useFormContext } from 'react-hook-form'
import type { ProfileEnvironmentOptions } from '../../../shared/api/types'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import type { ProfileFormValues } from '../form-schema'

type Props = {
  name: 'locale' | 'timezone' | 'userAgent'
  label: string
  hint: string
  options: ProfileEnvironmentOptions['locales']
}

export function EnvironmentOptionField({ name, label, hint, options }: Props) {
  const { control, setFocus } = useFormContext<ProfileFormValues>()
  const { field, fieldState: { error } } = useController({ control, name })
  const [manual, setManual] = useState(false)
  const focusAfterSwitch = useRef(false)
  const switchMode = (next: boolean) => {
    focusAfterSwitch.current = true
    setManual(next)
  }
  useEffect(() => {
    if (focusAfterSwitch.current) {
      setFocus(name)
      focusAfterSwitch.current = false
    }
  }, [manual, name, setFocus])
  const id = `profile-${name === 'userAgent' ? 'user-agent' : name}`
  const accessibility = {
    id,
    'aria-invalid': Boolean(error),
    'aria-describedby': `${id}-${error ? 'error' : 'hint'}`,
  }
  const unlisted = field.value && !options.some((option) => option.value === field.value)

  return <div className="grid content-start gap-2">
    <FormField label={label} htmlFor={id} error={error?.message} hint={hint}>
      {manual ? <Input {...field} {...accessibility} className="min-w-0 w-full" /> : <Select
        {...field}
        {...accessibility}
        className="min-w-0 w-full"
        onChange={(event) => {
          if (event.target.value === '__custom__') switchMode(true)
          else field.onChange(event)
        }}
      >
        <option value="">{name === 'userAgent' ? '跟随浏览器（推荐）' : '跟随浏览器（未指定）'}</option>
        {unlisted ? <option value={field.value}>{name === 'userAgent' ? '当前 User Agent（自定义或其他版本）' : `${field.value}（当前值）`}</option> : null}
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        <option value="__custom__">自定义…</option>
      </Select>}
    </FormField>
    {manual ? <Button type="button" variant="ghost" onClick={() => switchMode(false)} aria-label={`选择${label}预设`}>选择预设</Button> : null}
  </div>
}
