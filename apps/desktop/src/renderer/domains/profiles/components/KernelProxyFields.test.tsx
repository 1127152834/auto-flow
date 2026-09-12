import { chooseOption, choiceTestEnvironment, choiceValue } from '../../../shared/testing/choice-user'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FormProvider, useForm, useWatch } from 'react-hook-form'
import { afterEach, expect, it, vi } from 'vitest'
import type { InstalledKernel, ProxyOptionsRead } from '../../../shared/api/types'
import { emptyProfileForm, type ProfileFormValues } from '../form-schema'
import { KernelProxyFields, type KernelProxyFieldsProps } from './KernelProxyFields'

afterEach(cleanup)

const installedKernels: InstalledKernel[] = [
  { edition: 'public', version: '146.0.1.0', executablePath: '/public', size: 1 },
  { edition: 'licensed', version: '146.0.1.1', executablePath: '/licensed', size: 1 },
]
const proxyOptions: ProxyOptionsRead = {
  proxies: [{ id: 'proxy-1', name: '固定一号', enabled: true }],
  pools: [{ id: 'pool-1', name: '代理池一号' }],
}

function Harness(props: Partial<KernelProxyFieldsProps> = {}) {
  const form = useForm<ProfileFormValues>({ defaultValues: { ...emptyProfileForm, browserKernel: 'licensed|146.0.1.1' } })
  const values = useWatch({ control: form.control })
  return <FormProvider {...form}>
    <KernelProxyFields installedKernels={installedKernels} proxyOptions={proxyOptions} onManageKernel={() => undefined} {...props} />
    <output data-testid="values">{JSON.stringify(values)}</output>
  </FormProvider>
}

it('normalizes Preview to Stable when switching to a public kernel', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  await chooseOption(user, screen.getByLabelText('发布通道'), 'preview')
  await chooseOption(user, screen.getByLabelText('浏览器内核'), 'public|146.0.1.0')
  expect(choiceValue(screen.getByLabelText('发布通道'))).toBe('stable')
  expect(screen.getByLabelText('发布通道')).toBeDisabled()
})

it('clears mutually exclusive proxy references as the mode changes', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  await chooseOption(user, screen.getByLabelText('代理模式'), 'proxy')
  await chooseOption(user, screen.getByLabelText('固定代理'), 'proxy-1')
  expect(screen.getByTestId('values')).toHaveTextContent('"proxyId":"proxy-1"')
  await chooseOption(user, screen.getByLabelText('代理模式'), 'pool')
  expect(screen.getByTestId('values')).toHaveTextContent('"proxyId":""')
  await chooseOption(user, screen.getByLabelText('代理池'), 'pool-1')
  await chooseOption(user, screen.getByLabelText('代理模式'), 'none')
  expect(screen.getByTestId('values')).toHaveTextContent('"proxyPoolId":""')
})

it('binds all runtime switches through Controller', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  await user.click(screen.getByRole('switch', { name: '无头模式' }))
  await user.click(screen.getByRole('switch', { name: 'GeoIP' }))
  await user.click(screen.getByRole('switch', { name: '人类行为模拟' }))
  expect(screen.getByTestId('values')).toHaveTextContent('"headless":true')
  expect(screen.getByTestId('values')).toHaveTextContent('"geoip":true')
  expect(screen.getByTestId('values')).toHaveTextContent('"humanize":true')
})

it('keeps kernel management available when resources are empty or failed', async () => {
  const user = userEvent.setup()
  let trigger: HTMLButtonElement | null = null
  const onManageKernel = vi.fn<NonNullable<KernelProxyFieldsProps['onManageKernel']>>((event) => { trigger = event.currentTarget })
  render(<Harness installedKernels={[]} proxyOptions={{ proxies: [], pools: [] }} kernelsError="读取内核失败" onManageKernel={onManageKernel} />)
  screen.getByLabelText('浏览器内核').focus(); await user.keyboard('{ArrowDown}')
  expect(screen.getByRole('option', { name: '暂无已安装内核' })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.getByRole('alert')).toHaveTextContent('读取内核失败')
  await user.click(screen.getByRole('button', { name: '管理内核' }))
  expect(onManageKernel).toHaveBeenCalledTimes(1)
  expect(trigger).toBeInstanceOf(HTMLButtonElement)
})

it('keeps an invalid saved resource visible so the schema can block it', () => {
  function InvalidHarness() {
    const form = useForm<ProfileFormValues>({ defaultValues: { ...emptyProfileForm, browserKernel: 'public|removed', proxyMode: 'proxy', proxyId: 'removed-proxy' } })
    return <FormProvider {...form}><KernelProxyFields installedKernels={[]} proxyOptions={{ proxies: [], pools: [] }} onManageKernel={() => undefined} /></FormProvider>
  }
  render(<InvalidHarness />)
  expect(screen.getByLabelText('浏览器内核')).toHaveTextContent(/public · removed.*已不可用/)
  expect(screen.getByLabelText('固定代理')).toHaveTextContent(/removed-proxy.*已不可用/)
})

choiceTestEnvironment()
