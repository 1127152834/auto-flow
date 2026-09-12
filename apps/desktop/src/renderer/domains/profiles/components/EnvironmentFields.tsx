import { Controller, useFormContext, useWatch } from 'react-hook-form'
import type { ProfileEnvironmentOptions } from '../../../shared/api/types'
import { FormField } from '../../../shared/components/FormField'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { parseKernelKey, type ProfileFormValues } from '../form-schema'
import {
  buildChromiumUserAgentPresets,
  COLOR_SCHEME_PRESETS,
  getViewportPreset,
  HUMAN_PRESETS,
  VIEWPORT_PRESETS,
} from '../presets'
import { EnvironmentOptionField } from './EnvironmentOptionField'

type Props = {
  options?: ProfileEnvironmentOptions
  optionsLoading: boolean
  optionsError: string | null
  onRetryOptions(): void
}

export function EnvironmentFields({ options, optionsLoading, optionsError, onRetryOptions }: Props) {
  const { clearErrors, control, setValue, formState: { errors } } = useFormContext<ProfileFormValues>()
  const browserKernel = useWatch({ control, name: 'browserKernel' })
  const viewportMode = useWatch({ control, name: 'viewportMode' })
  const viewportWidth = useWatch({ control, name: 'viewportWidth' })
  const viewportHeight = useWatch({ control, name: 'viewportHeight' })
  const customViewport = viewportMode === 'custom'
  const browserVersion = parseKernelKey(browserKernel)?.version ?? ''
  const userAgent = useWatch({ control, name: 'userAgent' })
  const userAgentPresets = buildChromiumUserAgentPresets(browserVersion, options?.userAgentTemplates ?? [])
  const userAgentMajor = userAgent.match(/Chrome\/(\d+)\./)?.[1]
  const userAgentVersionMismatch = userAgentMajor && browserVersion && userAgentMajor !== browserVersion.split('.')[0]

  const selectViewport = (value: string) => {
    clearErrors('viewportMode')
    if (!value) {
      setValue('viewportMode', 'browser', { shouldDirty: true, shouldValidate: true })
      return
    }
    const [width, height] = value.split('x')
    if (!width || !height) return
    setValue('viewportMode', 'preset', { shouldDirty: true, shouldValidate: true })
    setValue('viewportWidth', width, { shouldDirty: true, shouldValidate: true })
    setValue('viewportHeight', height, { shouldDirty: true, shouldValidate: true })
  }
  const viewportPreset = getViewportPreset(viewportWidth, viewportHeight)

  return <section aria-labelledby="profile-environment-fields" className="grid gap-5">
    <div>
      <h2 id="profile-environment-fields" className="m-0 text-lg font-semibold text-ink">浏览器环境</h2>
      <p className="mb-0 mt-1 text-sm text-muted">预设可以直接选择，语言、时区和 User Agent 也可以手动输入。</p>
    </div>
    {optionsLoading ? <p role="status" className="m-0 text-sm text-muted">正在加载浏览器环境选项…</p> : null}
    {optionsError ? <div role="alert" className="flex items-center justify-between gap-3 text-sm text-clay">
      <span>浏览器环境选项加载失败：{optionsError}。可重试或选择自定义输入。</span>
      <Button type="button" onClick={onRetryOptions}>重新加载选项</Button>
    </div> : null}
    <div className="grid gap-4 sm:grid-cols-2">
      <EnvironmentOptionField name="locale" label="浏览器语言" hint="选择常用语言，或自定义 BCP 47 语言标记。" options={options?.locales ?? []} />
      <EnvironmentOptionField name="timezone" label="浏览器时区" hint="选择常用时区，或自定义 IANA 时区标识。" options={options?.timezones ?? []} />
    </div>
    <div className="grid gap-3 rounded-control border border-line bg-surface-subtle p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><span className="text-sm font-medium text-ink">浏览器视口</span><p className="mb-0 mt-1 text-xs text-muted">宽 320–7680、高 240–4320 像素。</p></div>
        <label className="flex items-center gap-2 text-sm text-ink">自定义尺寸<Switch aria-label="自定义尺寸" checked={customViewport} onCheckedChange={(checked) => {
          clearErrors('viewportMode')
          if (checked) {
            if (!viewportWidth || !viewportHeight) {
              const [width = '1280', height = '800'] = VIEWPORT_PRESETS[0]!.value.split('x')
              setValue('viewportWidth', width, { shouldDirty: true, shouldValidate: true })
              setValue('viewportHeight', height, { shouldDirty: true, shouldValidate: true })
            }
            setValue('viewportMode', 'custom', { shouldDirty: true, shouldValidate: true })
          } else if (viewportPreset) {
            setValue('viewportMode', 'preset', { shouldDirty: true, shouldValidate: true })
          } else {
            selectViewport(VIEWPORT_PRESETS[0]!.value)
          }
        }} /></label>
      </div>
      {customViewport ? <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-3">
        <FormField label="视口宽" htmlFor="profile-viewport-width" error={errors.viewportWidth?.message ?? errors.viewportMode?.message}>
          <Controller control={control} name="viewportWidth" render={({ field }) => <Input {...field} data-profile-viewport-focus id="profile-viewport-width" inputMode="numeric" aria-invalid={Boolean(errors.viewportWidth || errors.viewportMode)} aria-describedby={errors.viewportWidth || errors.viewportMode ? 'profile-viewport-width-error' : undefined} />} />
        </FormField>
        <span className="mt-9 text-muted" aria-hidden="true">×</span>
        <FormField label="视口高" htmlFor="profile-viewport-height" error={errors.viewportHeight?.message}>
          <Controller control={control} name="viewportHeight" render={({ field }) => <Input {...field} id="profile-viewport-height" inputMode="numeric" aria-invalid={Boolean(errors.viewportHeight)} aria-describedby={errors.viewportHeight ? 'profile-viewport-height-error' : undefined} />} />
        </FormField>
      </div> : <Select data-profile-viewport-focus aria-label="视口预设" aria-invalid={Boolean(errors.viewportMode)} aria-describedby={errors.viewportMode ? 'profile-viewport-error' : undefined} value={viewportMode === 'browser' ? '' : viewportPreset || VIEWPORT_PRESETS[0]!.value} onChange={(event) => selectViewport(event.target.value)} className="w-full">
        <option value="">跟随浏览器（未指定）</option>
        {VIEWPORT_PRESETS.map((preset) => <option key={preset.value} value={preset.value}>{preset.label}</option>)}
      </Select>}
      {!customViewport && errors.viewportMode?.message ? <p id="profile-viewport-error" role="alert" className="m-0 text-xs text-clay">{errors.viewportMode.message}</p> : null}
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="色彩模式" htmlFor="profile-color-scheme" hint="留空时跟随系统偏好。">
        <Controller control={control} name="colorScheme" render={({ field }) => <Select {...field} id="profile-color-scheme" aria-describedby="profile-color-scheme-hint" className="w-full">{COLOR_SCHEME_PRESETS.map((preset) => <option key={preset.value || 'system'} value={preset.value}>{preset.label}</option>)}</Select>} />
      </FormField>
      <FormField label="人类行为预设" htmlFor="profile-human-preset" hint="CloakBrowser 支持标准与谨慎两种节奏。">
        <Controller control={control} name="humanPreset" render={({ field }) => <Select {...field} id="profile-human-preset" aria-describedby="profile-human-preset-hint" className="w-full">{HUMAN_PRESETS.map((preset) => <option key={preset.value} value={preset.value}>{preset.label}</option>)}</Select>} />
      </FormField>
    </div>
    <div className="grid gap-2">
      <EnvironmentOptionField name="userAgent" label="User Agent" options={userAgentPresets} hint={browserVersion
        ? `预设匹配内核版本 ${browserVersion}；跟随浏览器可使用内核默认值。`
        : '选择内核后提供桌面预设，也可跟随浏览器或自定义输入。'} />
      {userAgent ? <p aria-label="当前 User Agent" className="m-0 break-all rounded-control border border-line bg-surface-subtle p-3 font-mono text-xs text-muted">{userAgent}</p> : null}
      {userAgentVersionMismatch ? <p role="status" className="m-0 text-xs text-clay">当前 User Agent 的 Chromium {userAgentMajor} 与所选内核不一致，请重新选择预设或跟随浏览器。</p> : null}
    </div>
  </section>
}
