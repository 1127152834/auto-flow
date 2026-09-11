import { expect, it } from 'vitest'
import { buildChromiumUserAgentPresets, getViewportPreset } from './presets'

it('builds desktop UA presets from the selected kernel major version', () => {
  const presets = buildChromiumUserAgentPresets('146.0.1.1')
  expect(presets).toHaveLength(4)
  expect(presets.slice(1).every(({ value }) => value.includes('Chrome/146.0.0.0'))).toBe(true)
  expect(buildChromiumUserAgentPresets('latest')).toHaveLength(1)
})

it('recognizes only a listed viewport preset', () => {
  expect(getViewportPreset('1536', '864')).toBe('1536x864')
  expect(getViewportPreset('1111', '777')).toBe('')
})
