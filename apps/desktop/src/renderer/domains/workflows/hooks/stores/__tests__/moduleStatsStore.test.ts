import { describe, it, expect, beforeEach } from 'vitest'
import { useModuleStatsStore } from '../moduleStatsStore'
import type { ModuleType } from '../../../types/index'

const t = (s: string) => s as ModuleType
const seed = (stats: Record<string, unknown>) => useModuleStatsStore.setState({ stats: stats as never })

describe('moduleStatsStore.getQuickList', () => {
  beforeEach(() => {
    localStorage.clear()
    seed({})
  })

  it('没有使用记录时为空', () => {
    expect(useModuleStatsStore.getState().getQuickList()).toEqual([])
  })

  it('综合最近使用与使用频次排序', () => {
    seed({
      freq: { usageCount: 50, lastUsed: 100, isFavorite: false },
      recent: { usageCount: 1, lastUsed: 9000, isFavorite: false },
      both: { usageCount: 60, lastUsed: 9500, isFavorite: false },
      stale: { usageCount: 1, lastUsed: 10, isFavorite: false },
    })
    const list = useModuleStatsStore.getState().getQuickList()
    expect(list[0]).toBe('both')
    expect(list[list.length - 1]).toBe('stale')
    expect(new Set(list).size).toBe(list.length)
  })

  it('上限 12，可用 limit 调整', () => {
    const s: Record<string, unknown> = {}
    for (let i = 0; i < 20; i++) s[`m${i}`] = { usageCount: i + 1, lastUsed: i + 1, isFavorite: false }
    seed(s)
    expect(useModuleStatsStore.getState().getQuickList()).toHaveLength(12)
    expect(useModuleStatsStore.getState().getQuickList(undefined, 5)).toHaveLength(5)
  })

  it('只含内置模块：排除自定义模块与不在允许列表内的类型', () => {
    seed({
      custom_module: { usageCount: 99, lastUsed: 9999, isFavorite: false },
      a: { usageCount: 2, lastUsed: 2, isFavorite: false },
      b: { usageCount: 1, lastUsed: 1, isFavorite: false },
    })
    expect(useModuleStatsStore.getState().getQuickList()).toEqual(['a', 'b'])
    expect(useModuleStatsStore.getState().getQuickList([t('b')])).toEqual(['b'])
  })

  it('只收藏未使用的模块不算最近与常用；缺字段或非法数值的旧数据被忽略而不抛错', () => {
    seed({
      fav: { usageCount: 0, lastUsed: 0, isFavorite: true },
      old: { usageCount: 3 },
      bad: { usageCount: 'x', lastUsed: null, isFavorite: false },
      nul: null,
    })
    expect(() => useModuleStatsStore.getState().getQuickList()).not.toThrow()
    expect(useModuleStatsStore.getState().getQuickList()).toEqual(['old'])
  })

  it('旧版本 localStorage 数据重新加载后保留，不丢失', async () => {
    localStorage.setItem(
      'module-stats-storage',
      JSON.stringify({ state: { stats: { x: { usageCount: 4, lastUsed: 5, isFavorite: true } } }, version: 0 }),
    )
    await useModuleStatsStore.persist.rehydrate()
    expect(useModuleStatsStore.getState().stats).toHaveProperty('x')
    expect(useModuleStatsStore.getState().getQuickList()).toEqual(['x'])
    expect(useModuleStatsStore.getState().getStats(t('x')).isFavorite).toBe(true)
  })

  it('损坏的 JSON 回退为空且不抛错', async () => {
    localStorage.setItem('module-stats-storage', '{not json')
    seed({})
    await expect(useModuleStatsStore.persist.rehydrate()).resolves.not.toThrow()
    expect(useModuleStatsStore.getState().getQuickList()).toEqual([])
  })

  it('损坏的结构（stats 不是对象）也回退为空', async () => {
    localStorage.setItem('module-stats-storage', JSON.stringify({ state: { stats: 'oops' }, version: 0 }))
    await useModuleStatsStore.persist.rehydrate()
    expect(() => useModuleStatsStore.getState().getQuickList()).not.toThrow()
    expect(useModuleStatsStore.getState().getQuickList()).toEqual([])
  })
})
