// @vitest-environment node
import { afterEach, describe, expect, it } from 'vitest'
import { hydrateAssistantArtifacts, readAssistantArtifact } from '../api/assistantArtifacts'
import { configureStudioConnection } from '../api/config'

let restore: (() => void) | undefined
afterEach(() => { restore?.(); restore = undefined })

describe('小助手产物引用', () => {
  it('通过 AutoFlow 受控传输读取图片而不把 base64 放进会话', async () => {
    restore = configureStudioConnection('http://127.0.0.1:1234', async (input) => {
      expect(String(input)).toBe('http://127.0.0.1:1234/api/ai-assistant/artifacts/attachment/image.png')
      return new Response(new Uint8Array([1, 2, 3]), { headers: { 'content-type': 'image/png' } })
    })

    const blob = await readAssistantArtifact('assistant-attachment://image.png')

    expect(blob.type).toBe('image/png')
    expect(Array.from(new Uint8Array(await blob.arrayBuffer()))).toEqual([1, 2, 3])
  })

  it('在执行前递归恢复大工具参数', async () => {
    restore = configureStudioConnection('http://127.0.0.1:1234', async () =>
      new Response(JSON.stringify({ text: '完整内容', count: 7 }), {
        headers: { 'content-type': 'application/json' },
      }),
    )

    const value = await hydrateAssistantArtifacts({
      nested: {
        artifactRef: 'assistant-artifact://large.json',
        mediaType: 'application/json',
        size: 70_000,
      },
    })

    expect(value).toEqual({ nested: { text: '完整内容', count: 7 } })
  })

  it('拒绝任意 URL 和目录穿越标识', async () => {
    restore = configureStudioConnection('http://127.0.0.1:1234', async () => new Response())
    await expect(readAssistantArtifact('https://outside.test/data')).rejects.toThrow('标识无效')
    await expect(readAssistantArtifact('assistant-artifact://../secret')).rejects.toThrow('标识无效')
  })
})
