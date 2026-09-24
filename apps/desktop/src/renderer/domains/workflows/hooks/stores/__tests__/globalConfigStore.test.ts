// Source: WebRPA@5ccb900e, store/__tests__/globalConfigStore.test.ts; see SOURCE.md for license and adaptation boundaries.
import { describe, it, expect, beforeEach, beforeAll, vi } from 'vitest'

// 该 store 使用 persist(localStorage) 中间件；jsdom 环境的 localStorage 在本 vitest
// 版本下 setItem 不可用。这里用内存实现打桩，并在打桩后再动态 import store，
// 确保 store 创建时 localStorage 已可用。
const _mem: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: (k: string) => (k in _mem ? _mem[k] : null),
  setItem: (k: string, v: string) => { _mem[k] = String(v) },
  removeItem: (k: string) => { delete _mem[k] },
  clear: () => { for (const k of Object.keys(_mem)) delete _mem[k] },
  key: () => null,
  get length() { return Object.keys(_mem).length },
})

type Store = typeof import('../globalConfigStore').useGlobalConfigStore
let S: Store

beforeAll(async () => {
  const mod = await import('../globalConfigStore')
  S = mod.useGlobalConfigStore
})

describe('globalConfigStore 小助手主应用模型边界', () => {
  beforeEach(() => {
    S.getState().updateAIAssistantConfig({
      modelId: 'managed-model',
      temperature: 0.7,
      enableTools: true,
    })
  })

  it('partial 更新保留未提供字段', () => {
    S.getState().updateAIAssistantConfig({ temperature: 0.3 })
    const a = S.getState().config.aiAssistant
    expect(a.temperature).toBe(0.3)
    expect(a.modelId).toBe('managed-model')
    expect(a.enableTools).toBe(true)
  })

  it('导入旧配置时丢弃渲染进程中的供应商密钥', () => {
    expect(S.getState().importConfig({
      aiAssistant: { apiUrl: 'https://legacy.invalid', apiKey: 'secret', model: 'legacy' },
    })).toBe(true)
    expect(JSON.stringify(S.getState().config.aiAssistant)).not.toMatch(/secret|apiKey|apiUrl/)
  })
})
