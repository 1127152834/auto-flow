import { documents } from '../components/documentation/documents'
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

it.each(['excel', 'word', 'desktop', 'input', 'image', 'files', 'pdf', 'media', 'phone', 'bots', 'sap', 'feishu'])('does not expose the excluded %s guide through navigation or loading', async topic => {
  expect(documents.some(document => document.id === `${topic}-guide`)).toBe(false)
  expect(await loadDocContent(`${topic}-guide`)).toBe('')
})
it('keeps shared notification and speech tools while removing excluded tutorial sections', async () => {
  const notifications = await loadDocContent('notifications-guide')
  expect(notifications).toContain('## 语音播报')
  expect(notifications).toContain('## 用户输入')
  expect(notifications).not.toMatch(/^## (播放音乐|播放视频|查看图片|媒体播放)/m)
  expect(documents.some(document => document.id === 'module-reference')).toBe(true)
  const reference = await loadDocContent('module-reference')
  expect(reference).toContain('## 数据库模块')
  expect(reference).toContain('### SSH 远程')
  expect(reference).not.toMatch(/^#{2,3} (Excel|桌面|媒体|文档与文件|QQ 机器人|飞书|SAP)/m)
  expect(await loadDocContent('notify-guide')).not.toContain('notify_feishu')
  expect(await loadDocContent('utils-guide')).not.toContain('file_hash_compare')
})
