import { afterEach, expect, it, vi } from 'vitest'
import { documentContents, getCachedContent, loadAllContents, loadDocContent } from '../components/documentation/contents'

afterEach(() => vi.unstubAllGlobals())
it('loads Chinese documentation even with an English browser and a legacy English preference', async () => {
  vi.stubGlobal('navigator', { language: 'en-US' })
  vi.stubGlobal('localStorage', { getItem: () => 'en' })
  const text = await loadDocContent('getting-started')
  expect(text).toContain('快速入门')
  expect(getCachedContent('getting-started')).toBe(text)
  expect(documentContents['getting-started']).toBe(text)
})
it('lazily loads Chinese documents for search and reuses their cached content', async () => {
  const results = await loadAllContents(['browser-guide', 'variables-guide'])
  expect(results['browser-guide']).toMatch(/[\u4e00-\u9fff]/)
  expect(results['variables-guide']).toMatch(/[\u4e00-\u9fff]/)
  expect(await loadDocContent('browser-guide')).toBe(results['browser-guide'])
  expect(documentContents['variables-guide']).toBe(results['variables-guide'])
})
it('handles a missing document without inventing content', async () => {
  expect(await loadDocContent('unknown-document')).toBe('')
})
