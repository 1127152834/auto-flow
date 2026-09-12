import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { afterEach, expect, it, vi } from 'vitest'
import { emptyProfileForm, type ProfileFormValues } from '../form-schema'
import { EnvironmentFields } from './EnvironmentFields'

afterEach(cleanup)

const options = {
  locales: [{ value: 'zh-CN', label: '中文' }, { value: 'ja-JP', label: '日语' }],
  timezones: [{ value: 'Asia/Shanghai', label: '上海' }, { value: 'Asia/Tokyo', label: '东京' }],
  userAgentTemplates: [{ value: 'Server UA Chrome/{major}.0.0.0', label: '后端 UA · Chromium {major}' }],
}

function Harness({ initial = emptyProfileForm, loading = false, error = null, retry = () => {} }: { initial?: ProfileFormValues; loading?: boolean; error?: string | null; retry?: () => void }) {
  const form = useForm<ProfileFormValues>({ defaultValues: { ...initial, browserKernel: 'licensed|146.0.1.1' } })
  const values = useWatch({ control: form.control })
  return <FormProvider {...form}><EnvironmentFields options={loading || error ? undefined : options} optionsLoading={loading} optionsError={error} onRetryOptions={retry} /><button onClick={() => form.setValue('browserKernel', 'public|147.0.1.1')}>切换测试内核</button><button onClick={() => form.setValue('browserKernel', '')}>取消测试内核</button><output data-testid="values">{JSON.stringify(values)}</output></FormProvider>
}

it('offers all server options despite current defaults and supports custom input', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  expect(screen.getByLabelText('浏览器语言')).toHaveValue('zh-CN')
  await user.selectOptions(screen.getByLabelText('浏览器语言'), 'ja-JP')
  await user.selectOptions(screen.getByLabelText('浏览器时区'), 'Asia/Tokyo')
  expect(screen.getByTestId('values')).toHaveTextContent('"locale":"ja-JP"')
  expect(screen.getByTestId('values')).toHaveTextContent('"timezone":"Asia/Tokyo"')
  await user.selectOptions(screen.getByLabelText('浏览器语言'), '__custom__')
  await user.selectOptions(screen.getByLabelText('浏览器时区'), '__custom__')
  const locale = screen.getByLabelText('浏览器语言')
  const timezone = screen.getByLabelText('浏览器时区')
  await user.clear(locale)
  await user.type(locale, 'de-CH-1901')
  await user.clear(timezone)
  await user.type(timezone, 'Europe/Zurich')
  expect(screen.getByTestId('values')).toHaveTextContent('"locale":"de-CH-1901"')
  expect(screen.getByTestId('values')).toHaveTextContent('"timezone":"Europe/Zurich"')
  await user.click(screen.getByRole('button', { name: '选择浏览器语言预设' }))
  expect(screen.getByLabelText('浏览器语言')).toHaveValue('de-CH-1901')
  await user.selectOptions(screen.getByLabelText('浏览器语言'), '')
  expect(screen.getByTestId('values')).toHaveTextContent('"locale":""')
})

it('keeps unlisted saved values while the catalog loads or fails, and offers retry', async () => {
  const user = userEvent.setup()
  const retry = vi.fn()
  const initial = { ...emptyProfileForm, locale: 'de-CH-1901', timezone: 'Europe/Zurich' }
  const { rerender } = render(<Harness initial={initial} loading />)
  expect(screen.getByText('正在加载浏览器环境选项…')).toHaveAttribute('role', 'status')
  expect(screen.queryByRole('option', { name: '日语' })).not.toBeInTheDocument()
  expect(screen.queryByRole('option', { name: '后端 UA · Chromium 146' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('浏览器语言')).toHaveValue(initial.locale)
  rerender(<Harness initial={initial} error="连接失败" retry={retry} />)
  expect(screen.getByRole('alert')).toHaveTextContent('连接失败')
  expect(screen.getByLabelText('浏览器时区')).toHaveValue(initial.timezone)
  await user.click(screen.getByRole('button', { name: '重新加载选项' }))
  expect(retry).toHaveBeenCalledOnce()
  rerender(<Harness initial={initial} />)
  expect(screen.getByRole('option', { name: '日语' })).toBeInTheDocument()
  expect(screen.getByLabelText('浏览器时区')).toHaveValue(initial.timezone)
})

it('applies viewport presets and supports custom integer dimensions', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  await user.selectOptions(screen.getByLabelText('视口预设'), '1920x1080')
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportWidth":"1920"')
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportHeight":"1080"')
  await user.click(screen.getByRole('switch', { name: '自定义尺寸' }))
  await user.clear(screen.getByLabelText('视口宽'))
  await user.type(screen.getByLabelText('视口宽'), '1441')
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportWidth":"1441"')
})

it('moves an unspecified viewport explicitly to a preset or custom size', async () => {
  const user = userEvent.setup()
  render(<Harness initial={{ ...emptyProfileForm, viewportMode: 'browser', viewportWidth: '', viewportHeight: '' }} />)
  expect(screen.getByLabelText('视口预设')).toHaveValue('')
  await user.selectOptions(screen.getByLabelText('视口预设'), '1920x1080')
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportMode":"preset"')
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportWidth":"1920"')

  cleanup()
  render(<Harness initial={{ ...emptyProfileForm, viewportMode: 'browser', viewportWidth: '', viewportHeight: '' }} />)
  await user.click(screen.getByRole('switch', { name: '自定义尺寸' }))
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportMode":"custom"')
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportWidth":"1280"')
  expect(screen.getByTestId('values')).toHaveTextContent('"viewportHeight":"800"')
  expect(screen.getByLabelText('视口宽')).toBeInTheDocument()
  expect(screen.getByLabelText('视口高')).toBeInTheDocument()
})

it('offers a kernel-major UA preset and binds environment preferences', async () => {
  const user = userEvent.setup()
  const { container } = render(<Harness />)
  expect(container.querySelector('option[value*="Chrome/146.0.0.0"]')).toBeInTheDocument()
  expect(screen.getByLabelText('User Agent')).toHaveValue('')
  await user.selectOptions(screen.getByLabelText('User Agent'), 'Server UA Chrome/146.0.0.0')
  expect(screen.getByLabelText('当前 User Agent')).toHaveTextContent('Server UA Chrome/146.0.0.0')
  await user.selectOptions(screen.getByLabelText('色彩模式'), 'dark')
  await user.selectOptions(screen.getByLabelText('人类行为预设'), 'careful')
  await user.selectOptions(screen.getByLabelText('User Agent'), '__custom__')
  await user.clear(screen.getByLabelText('User Agent'))
  await user.type(screen.getByLabelText('User Agent'), 'Custom UA')
  expect(screen.getByTestId('values')).toHaveTextContent('"colorScheme":"dark"')
  expect(screen.getByTestId('values')).toHaveTextContent('"humanPreset":"careful"')
  expect(screen.getByTestId('values')).toHaveTextContent('"userAgent":"Custom UA"')
  await user.click(screen.getByRole('button', { name: '选择User Agent预设' }))
  expect(screen.getByLabelText('User Agent')).toHaveValue('Custom UA')
  await user.selectOptions(screen.getByLabelText('User Agent'), '')
  expect(screen.getByTestId('values')).toHaveTextContent('"userAgent":""')
  expect(screen.queryByLabelText('当前 User Agent')).not.toBeInTheDocument()
})

it('refreshes UA choices on kernel changes without overwriting saved or custom UA values', async () => {
  const user = userEvent.setup()
  render(<Harness initial={{ ...emptyProfileForm, userAgent: 'Server UA Chrome/146.0.0.0' }} />)
  await user.click(screen.getByRole('button', { name: '切换测试内核' }))
  expect(screen.getByRole('option', { name: '后端 UA · Chromium 147' })).toBeInTheDocument()
  expect(screen.getByLabelText('User Agent')).toHaveValue('Server UA Chrome/146.0.0.0')
  expect(screen.getByText(/当前 User Agent 的 Chromium 146 与所选内核不一致/)).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('User Agent'), 'Server UA Chrome/147.0.0.0')
  expect(screen.queryByText(/与所选内核不一致/)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '取消测试内核' }))
  expect(screen.queryByRole('option', { name: '后端 UA · Chromium 147' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('User Agent')).toHaveValue('Server UA Chrome/147.0.0.0')
})
