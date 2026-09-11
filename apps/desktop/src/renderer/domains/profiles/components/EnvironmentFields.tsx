import { useId, useState } from 'react'
import { Controller, useFormContext, useWatch } from 'react-hook-form'
import { FormField } from '../../../shared/components/FormField'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { parseKernelKey, type ProfileFormValues } from '../form-schema'
import {
  buildChromiumUserAgentPresets,
  COLOR_SCHEME_PRESETS,
  getViewportPreset,
  HUMAN_PRESETS,
  LOCALE_PRESETS,
  TIMEZONE_PRESETS,
  VIEWPORT_PRESETS,
} from '../presets'

export function EnvironmentFields() {
  const { control, getValues, setValue, formState: { errors } } = useFormContext<ProfileFormValues>()
  const localeList = useId()
  const timezoneList = useId()
  const userAgentList = useId()
  const browserKernel = useWatch({ control, name: 'browserKernel' })
  const [customViewport, setCustomViewport] = useState(() => !getViewportPreset(getValues('viewportWidth'), getValues('viewportHeight')))
  const userAgentPresets = buildChromiumUserAgentPresets(parseKernelKey(browserKernel)?.version ?? '')

  const selectViewport = (value: string) => {
    const [width, height] = value.split('x')
    if (!width || !height) return
    setValue('viewportWidth', width, { shouldDirty: true, shouldValidate: true })
    setValue('viewportHeight', height, { shouldDirty: true, shouldValidate: true })
  }
  const viewportPreset = getViewportPreset(
    useWatch({ control, name: 'viewportWidth' }),
    useWatch({ control, name: 'viewportHeight' }),
  )

  return <section aria-labelledby="profile-environment-fields" className="grid gap-5">
    <div>
      <h2 id="profile-environment-fields" className="m-0 text-lg font-semibold text-ink">浏览器环境</h2>
      <p className="mb-0 mt-1 text-sm text-muted">预设可以直接选择，语言、时区和 User Agent 也可以手动输入。</p>
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="浏览器语言" htmlFor="profile-locale" error={errors.locale?.message} hint="BCP 47 语言标记，例如 zh-CN。">
        <Controller control={control} name="locale" render={({ field }) => <><Input {...field} id="profile-locale" aria-describedby={errors.locale ? 'profile-locale-error' : 'profile-locale-hint'} aria-invalid={Boolean(errors.locale)} list={localeList} placeholder="例如 zh-CN" /><datalist id={localeList}>{LOCALE_PRESETS.map((preset) => <option key={preset.value} value={preset.value}>{preset.label}</option>)}</datalist></>} />
      </FormField>
      <FormField label="浏览器时区" htmlFor="profile-timezone" error={errors.timezone?.message} hint="IANA 时区，例如 Asia/Shanghai。">
        <Controller control={control} name="timezone" render={({ field }) => <><Input {...field} id="profile-timezone" aria-describedby={errors.timezone ? 'profile-timezone-error' : 'profile-timezone-hint'} aria-invalid={Boolean(errors.timezone)} list={timezoneList} placeholder="例如 Asia/Shanghai" /><datalist id={timezoneList}>{TIMEZONE_PRESETS.map((preset) => <option key={preset.value} value={preset.value}>{preset.label}</option>)}</datalist></>} />
      </FormField>
    </div>
    <div className="grid gap-3 rounded-control border border-line bg-surface-subtle p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><span className="text-sm font-medium text-ink">浏览器视口</span><p className="mb-0 mt-1 text-xs text-muted">宽 320–7680、高 240–4320 像素。</p></div>
        <label className="flex items-center gap-2 text-sm text-ink">自定义尺寸<Switch aria-label="自定义尺寸" checked={customViewport} onCheckedChange={(checked) => {
          setCustomViewport(checked)
          if (!checked && !viewportPreset) selectViewport(VIEWPORT_PRESETS[0]!.value)
        }} /></label>
      </div>
      {customViewport ? <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-3">
        <FormField label="视口宽" htmlFor="profile-viewport-width" error={errors.viewportWidth?.message}>
          <Controller control={control} name="viewportWidth" render={({ field }) => <Input {...field} id="profile-viewport-width" inputMode="numeric" aria-invalid={Boolean(errors.viewportWidth)} aria-describedby={errors.viewportWidth ? 'profile-viewport-width-error' : undefined} />} />
        </FormField>
        <span className="mt-9 text-muted" aria-hidden="true">×</span>
        <FormField label="视口高" htmlFor="profile-viewport-height" error={errors.viewportHeight?.message}>
          <Controller control={control} name="viewportHeight" render={({ field }) => <Input {...field} id="profile-viewport-height" inputMode="numeric" aria-invalid={Boolean(errors.viewportHeight)} aria-describedby={errors.viewportHeight ? 'profile-viewport-height-error' : undefined} />} />
        </FormField>
      </div> : <Select aria-label="视口预设" value={viewportPreset || VIEWPORT_PRESETS[0]!.value} onChange={(event) => selectViewport(event.target.value)} className="w-full">
        {VIEWPORT_PRESETS.map((preset) => <option key={preset.value} value={preset.value}>{preset.label}</option>)}
      </Select>}
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="色彩模式" htmlFor="profile-color-scheme" hint="留空时跟随系统偏好。">
        <Controller control={control} name="colorScheme" render={({ field }) => <Select {...field} id="profile-color-scheme" aria-describedby="profile-color-scheme-hint" className="w-full">{COLOR_SCHEME_PRESETS.map((preset) => <option key={preset.value || 'system'} value={preset.value}>{preset.label}</option>)}</Select>} />
      </FormField>
      <FormField label="人类行为预设" htmlFor="profile-human-preset" hint="CloakBrowser 支持标准与谨慎两种节奏。">
        <Controller control={control} name="humanPreset" render={({ field }) => <Select {...field} id="profile-human-preset" aria-describedby="profile-human-preset-hint" className="w-full">{HUMAN_PRESETS.map((preset) => <option key={preset.value} value={preset.value}>{preset.label}</option>)}</Select>} />
      </FormField>
    </div>
    <FormField label="User Agent" htmlFor="profile-user-agent" hint={browserKernel ? `预设匹配内核版本 ${parseKernelKey(browserKernel)?.version ?? ''}；留空时跟随浏览器。` : '选择内核后提供匹配主版本的桌面预设。'}>
      <Controller control={control} name="userAgent" render={({ field }) => <><Input {...field} id="profile-user-agent" aria-describedby="profile-user-agent-hint" list={userAgentList} placeholder="留空时跟随浏览器，或直接粘贴 User Agent" /><datalist id={userAgentList}>{userAgentPresets.map((preset) => <option key={preset.label} value={preset.value}>{preset.label}</option>)}</datalist></>} />
    </FormField>
  </section>
}
