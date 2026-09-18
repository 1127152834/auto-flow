import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import type { Automation } from '../types'
import { EnvironmentPolicyEditor } from './EnvironmentPolicyEditor'

choiceTestEnvironment()
afterEach(cleanup)
type Policy = Automation['environmentPolicy']
const profiles = [{ id: 'profile-a', name: '商品资料采集' }, { id: 'profile-b', name: '备用配置' }]
const proxies = [{ id: 'proxy-a', name: '上海代理' }, { id: 'proxy-b', name: '北京代理' }]
const pools = [{ id: 'pool-a', name: '采集代理池' }]
const internal = '11111111-2222-4333-8444-555555555555'
const props = (value: Policy = { source: 'newFromProfile' }) => ({ value, onChange: vi.fn(), profiles, proxies, pools })

it('switches between inherited and explicit profiles without retaining an old id', async () => {
  const p = props({ source: 'newFromProfile', profileId: 'profile-a' }), user = userEvent.setup()
  const view = render(<EnvironmentPolicyEditor {...p}/>)
  await chooseOption(user, screen.getByRole('combobox', { name: '浏览器配置来源' }), 'inherit')
  expect(p.onChange).toHaveBeenLastCalledWith({ source: 'newFromProfile' })
  view.rerender(<EnvironmentPolicyEditor {...p} value={{ source: 'newFromProfile' }}/>)
  await chooseOption(user, screen.getByRole('combobox', { name: '浏览器配置来源' }), 'specified')
  expect(p.onChange).toHaveBeenLastCalledWith({ source: 'newFromProfile', profileId: null })
})

it('selects a profile and preserves an unavailable saved profile until the user changes it', async () => {
  const missing = props({ source: 'newFromProfile', profileId: 'profile-missing' }), user = userEvent.setup()
  const view = render(<EnvironmentPolicyEditor {...missing}/>)
  expect(screen.getByRole('combobox', { name: '浏览器配置' })).toHaveAttribute('data-choice-value', 'profile-missing')
  expect(screen.getByText('已保存的浏览器配置引用暂不可用')).toBeVisible()
  expect(missing.onChange).not.toHaveBeenCalled()
  view.rerender(<EnvironmentPolicyEditor {...missing} />)
  await chooseOption(user, screen.getByRole('combobox', { name: '浏览器配置' }), 'profile-b')
  expect(missing.onChange).toHaveBeenCalledWith({ source: 'newFromProfile', profileId: 'profile-b' })
})

it('switches all proxy branches and removes ids from the previous branch', async () => {
  const p = props({ source: 'newFromProfile', profileId: 'profile-a', proxyOverride: { mode: 'fixed', proxyId: 'proxy-b' } }), user = userEvent.setup()
  const view = render(<EnvironmentPolicyEditor {...p}/>)
  const cases: Array<[string, Policy]> = [
    ['inherit', { source: 'newFromProfile', profileId: 'profile-a' }],
    ['sourceDefault', { source: 'newFromProfile', profileId: 'profile-a', proxyOverride: { mode: 'sourceDefault' } }],
    ['none', { source: 'newFromProfile', profileId: 'profile-a', proxyOverride: { mode: 'none' } }],
    ['fixed', { source: 'newFromProfile', profileId: 'profile-a', proxyOverride: { mode: 'fixed', proxyId: 'proxy-a' } }],
    ['pool', { source: 'newFromProfile', profileId: 'profile-a', proxyOverride: { mode: 'pool', proxyPoolId: 'pool-a' } }],
  ]
  let value = p.value
  for (const [mode, expected] of cases) {
    view.rerender(<EnvironmentPolicyEditor {...p} value={value}/>)
    await user.click(screen.getByRole('radio', { name: mode === 'inherit' ? '继承项目默认' : mode === 'sourceDefault' ? '跟随浏览器配置' : mode === 'none' ? '不使用代理' : mode === 'fixed' ? '固定代理' : '代理池' }))
    expect(p.onChange).toHaveBeenLastCalledWith(expected)
    value = expected
  }
})

it('keeps all three environment sources available', () => {
  const p = props()
  render(<EnvironmentPolicyEditor {...p} environments={[{ id: internal, name: '登录环境' }]} />)
  expect(screen.getByRole('radio', { name: '固定保存环境' })).toBeEnabled()
  expect(screen.getByRole('radio', { name: '使用记录关联环境' })).toBeEnabled()
  expect(screen.getByText('任务结束后关闭并清理临时环境，除非明确保留。')).toBeVisible()
  expect(screen.getByRole('combobox', { name: '模型提供方' })).toHaveAttribute('data-choice-value', 'inherit')
  expect(p.onChange).not.toHaveBeenCalled()
})

it('preserves a saved unsupported source and never coerces it on render', () => {
  const value: Policy = { source: 'fixedEnvironment', environmentId: internal, proxyOverride: { mode: 'none' } }
  const p = props(value)
  render(<EnvironmentPolicyEditor {...p}/>)
  expect(screen.getByRole('combobox', { name: '保存环境' })).toHaveAttribute('data-choice-value', internal)
  expect(document.body.textContent).not.toContain(internal)
  expect(p.onChange).not.toHaveBeenCalled()
})

it('shows a resolved input alias while keeping its internal identity hidden', () => {
  const businessUuidAlias = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
  render(<EnvironmentPolicyEditor
    {...props({ source: 'inputEnvironment', inputId: internal })}
    inputs={[{ inputId: internal, alias: businessUuidAlias }]}
  />)
  expect(screen.getByText(businessUuidAlias)).toBeVisible()
  expect(document.body.textContent).not.toContain(internal)
})

it('uses semantic labels for every unavailable saved resource', async () => {
  const user = userEvent.setup()
  const cases: Array<[Policy, string, string]> = [
    [{ source: 'newFromProfile', profileId: internal }, '浏览器配置', '已保存的浏览器配置引用暂不可用'],
    [{ source: 'newFromProfile', modelProviderId: internal }, '模型提供方', '已保存的模型提供方引用暂不可用'],
    [{ source: 'newFromProfile', proxyOverride: { mode: 'fixed', proxyId: internal } }, '固定代理', '已保存的代理引用暂不可用'],
    [{ source: 'newFromProfile', proxyOverride: { mode: 'pool', proxyPoolId: internal } }, '代理池', '已保存的代理池引用暂不可用'],
  ]
  for (const [value, label, unavailable] of cases) {
    const view = render(<EnvironmentPolicyEditor {...props(value)} />)
    const select = screen.getByRole('combobox', { name: label })
    expect(select).toHaveTextContent(unavailable)
    await user.click(select)
    expect(screen.getAllByRole('option').some(option => option.textContent?.includes(unavailable))).toBe(true)
    expect(document.body.textContent).not.toContain(internal)
    expect(select).not.toHaveAttribute('title', expect.stringContaining(internal))
    view.unmount()
  }
})

it('describes an unavailable saved data input without exposing its identity', () => {
  render(<EnvironmentPolicyEditor {...props({ source: 'inputEnvironment', inputId: internal })} />)
  expect(screen.getByText('已保存的数据输入引用暂不可用')).toBeVisible()
  expect(document.body.textContent).not.toContain(internal)
})

it('disables every mutation and associates external errors with controls', () => {
  const p = props({ source: 'newFromProfile', profileId: 'profile-a', proxyOverride: { mode: 'fixed', proxyId: 'proxy-a' } })
  render(<EnvironmentPolicyEditor {...p} disabled errors={{ profileId: '浏览器配置不可用', proxyId: '代理不可用' }}/>)
  expect(screen.getByRole('combobox', { name: '浏览器配置' })).toBeDisabled()
  expect(screen.getByRole('combobox', { name: '浏览器配置' })).toHaveAccessibleDescription('浏览器配置不可用')
  expect(screen.getByRole('combobox', { name: '固定代理' })).toHaveAccessibleDescription('代理不可用')
  for (const radio of screen.getAllByRole('radio')) expect(radio).toBeDisabled()
})

it('distinguishes inherited, explicit and absent model providers and preserves selection when changing profile source', async () => {
  const p = props(), user = userEvent.setup()
  const providers = [{ id: 'model-a', name: '内容处理模型' }]
  const view = render(<EnvironmentPolicyEditor {...p} modelProviders={providers}/>)
  await chooseOption(user, screen.getByRole('combobox', { name: '模型提供方' }), 'model-a')
  expect(p.onChange).toHaveBeenLastCalledWith({ source: 'newFromProfile', modelProviderId: 'model-a' })
  view.rerender(<EnvironmentPolicyEditor {...p} modelProviders={providers} value={{ source: 'newFromProfile', modelProviderId: 'model-a' }}/>)
  await chooseOption(user, screen.getByRole('combobox', { name: '浏览器配置来源' }), 'specified')
  expect(p.onChange).toHaveBeenLastCalledWith({ source: 'newFromProfile', profileId: null, modelProviderId: 'model-a' })
  await chooseOption(user, screen.getByRole('combobox', { name: '模型提供方' }), 'none')
  expect(p.onChange).toHaveBeenLastCalledWith({ source: 'newFromProfile', modelProviderId: null })
  await chooseOption(user, screen.getByRole('combobox', { name: '模型提供方' }), 'inherit')
  expect(p.onChange).toHaveBeenLastCalledWith({ source: 'newFromProfile' })
})
