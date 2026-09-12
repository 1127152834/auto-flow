import { expect, it } from 'vitest'
import { buildChromiumUserAgentPresets, getViewportPreset } from './presets'

it('builds desktop UA presets from the selected kernel major version', () => {
  const templates = [{ label: '服务端预设 · Chromium {major}', value: 'Server UA Chrome/{major}.0.0.0' }]
  expect(buildChromiumUserAgentPresets('146.0.1.1', templates)).toEqual([
    { label: '服务端预设 · Chromium 146', value: 'Server UA Chrome/146.0.0.0' },
  ])
  expect(buildChromiumUserAgentPresets('147.0.1.1', templates)[0]?.value).toBe('Server UA Chrome/147.0.0.0')
  expect(buildChromiumUserAgentPresets('146.0.1.1', [])).toEqual([])
  for (const version of ['', 'latest', '146invalid', '0.0.1', '146.0.1.1-extra']) {
    expect(buildChromiumUserAgentPresets(version, templates)).toEqual([])
  }
})

it('recognizes only a listed viewport preset', () => {
  expect(getViewportPreset('1536', '864')).toBe('1536x864')
  expect(getViewportPreset('1111', '777')).toBe('')
})
