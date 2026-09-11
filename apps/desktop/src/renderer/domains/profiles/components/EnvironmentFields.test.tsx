import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { afterEach, expect, it } from 'vitest'
import { emptyProfileForm, type ProfileFormValues } from '../form-schema'
import { EnvironmentFields } from './EnvironmentFields'

afterEach(cleanup)

function Harness() {
  const form = useForm<ProfileFormValues>({ defaultValues: { ...emptyProfileForm, browserKernel: 'licensed|146.0.1.1' } })
  const values = useWatch({ control: form.control })
  return <FormProvider {...form}><EnvironmentFields /><output data-testid="values">{JSON.stringify(values)}</output></FormProvider>
}

it('keeps locale and timezone editable while offering presets', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  const locale = screen.getByLabelText('浏览器语言')
  const timezone = screen.getByLabelText('浏览器时区')
  expect(locale).toHaveAttribute('list')
  expect(timezone).toHaveAttribute('list')
  await user.clear(locale)
  await user.type(locale, 'de-CH-1901')
  await user.clear(timezone)
  await user.type(timezone, 'Europe/Zurich')
  expect(screen.getByTestId('values')).toHaveTextContent('"locale":"de-CH-1901"')
  expect(screen.getByTestId('values')).toHaveTextContent('"timezone":"Europe/Zurich"')
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

it('offers a kernel-major UA preset and binds environment preferences', async () => {
  const user = userEvent.setup()
  const { container } = render(<Harness />)
  expect(container.querySelector('option[value*="Chrome/146.0.0.0"]')).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('色彩模式'), 'dark')
  await user.selectOptions(screen.getByLabelText('人类行为预设'), 'careful')
  await user.type(screen.getByLabelText('User Agent'), 'Custom UA')
  expect(screen.getByTestId('values')).toHaveTextContent('"colorScheme":"dark"')
  expect(screen.getByTestId('values')).toHaveTextContent('"humanPreset":"careful"')
  expect(screen.getByTestId('values')).toHaveTextContent('"userAgent":"Custom UA"')
})
