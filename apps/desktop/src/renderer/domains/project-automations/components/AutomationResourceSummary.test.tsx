import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { AutomationResourceSummary, type AutomationResourceSummaryProps } from './AutomationResourceSummary'

afterEach(cleanup)
const base: AutomationResourceSummaryProps = {
  policy: { source: 'newFromProfile' },
  projectDefaults: { profileId: 'profile-project', proxy: { mode: 'fixed', proxyId: 'proxy-project' }, modelProviderId: 'model-project' },
  profiles: [
    { id: 'profile-project', name: '项目浏览器', browserVersion: '128', browserEdition: 'Stable', proxyMode: 'proxy', proxyId: 'proxy-project' },
    { id: 'profile-direct', name: '自动化浏览器', browserVersion: '129', browserEdition: 'public', proxyMode: 'pool', proxyPoolId: 'pool-direct' },
  ],
  proxies: [{ id: 'proxy-project', name: '项目代理' }], pools: [{ id: 'pool-direct', name: '采集代理池' }], models: [{ id: 'model-project', name: '内容模型' }],
}
const row = (name: string) => screen.getByRole('row', { name: new RegExp(`^${name}`) })

it('resolves sourceDefault directly from the selected profile instead of project proxy defaults', () => {
  render(<AutomationResourceSummary {...base} policy={{ source: 'newFromProfile', profileId: 'profile-direct', proxyOverride: { mode: 'sourceDefault' } }}/>)
  expect(within(row('代理')).getByText('采集代理池')).toBeVisible()
  expect(within(row('代理')).getByText('浏览器配置')).toBeVisible()
  expect(within(row('代理')).queryByText('项目代理')).toBeNull()
  expect(within(row('CloakBrowser 内核')).getByText('公开版 · 129')).toBeVisible()
})

it('distinguishes an explicit null model from an inherited missing model reference', () => {
  const view = render(<AutomationResourceSummary {...base} policy={{ source: 'newFromProfile', modelProviderId: null }}/>)
  expect(row('模型')).toHaveTextContent('未配置自动化配置未配置')
  view.rerender(<AutomationResourceSummary {...base} policy={{ source: 'newFromProfile' }} projectDefaults={{ ...base.projectDefaults, modelProviderId: 'missing' }}/>)
  expect(row('模型')).toHaveTextContent('引用不可用项目默认引用不可用')
})

it('marks missing saved references without guessing availability', () => {
  render(<AutomationResourceSummary {...base} policy={{ source: 'newFromProfile', profileId: 'missing', proxyOverride: { mode: 'fixed', proxyId: 'missing' }, modelProviderId: 'missing' }}/>)
  expect(row('浏览器配置')).toHaveTextContent('引用不可用自动化配置引用不可用')
  expect(row('代理')).toHaveTextContent('引用不可用自动化配置引用不可用')
  expect(screen.queryByText('可用')).toBeNull()
})
