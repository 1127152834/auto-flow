// Source: WebRPA@5ccb900e, store/moduleStatsStore.ts; see SOURCE.md for license and adaptation boundaries.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { ModuleType } from '../../types/index'

interface ModuleStats {
  usageCount: number
  lastUsed: number
  isFavorite: boolean
  customColor?: string // 自定义标签颜色
}

interface ModuleStatsStore {
  stats: Partial<Record<ModuleType, ModuleStats>>
  
  // 增加使用次数
  incrementUsage: (moduleType: ModuleType) => void
  
  // 切换收藏状态
  toggleFavorite: (moduleType: ModuleType) => void
  
  // 设置自定义颜色
  setCustomColor: (moduleType: ModuleType, color: string | undefined) => void
  
  // 获取模块统计
  getStats: (moduleType: ModuleType) => ModuleStats
  
  // 获取排序后的模块列表
  getSortedModules: (modules: ModuleType[]) => ModuleType[]

  // 最近与常用：按最近使用与使用频次综合排序，仅内置模块，默认上限 12
  getQuickList: (allowed?: ModuleType[], limit?: number) => ModuleType[]
}

export const QUICK_LIST_LIMIT = 12
const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0)

const defaultStats: ModuleStats = {
  usageCount: 0,
  lastUsed: 0,
  isFavorite: false,
}

export const useModuleStatsStore = create<ModuleStatsStore>()(
  persist(
    (set, get) => ({
      stats: {},
      
      incrementUsage: (moduleType) => {
        set((state) => ({
          stats: {
            ...state.stats,
            [moduleType]: {
              ...defaultStats,
              ...state.stats[moduleType],
              usageCount: (state.stats[moduleType]?.usageCount || 0) + 1,
              lastUsed: Date.now(),
            },
          },
        }))
      },
      
      toggleFavorite: (moduleType) => {
        set((state) => ({
          stats: {
            ...state.stats,
            [moduleType]: {
              ...defaultStats,
              ...state.stats[moduleType],
              isFavorite: !(state.stats[moduleType]?.isFavorite || false),
            },
          },
        }))
      },
      
      setCustomColor: (moduleType, color) => {
        set((state) => ({
          stats: {
            ...state.stats,
            [moduleType]: {
              ...defaultStats,
              ...state.stats[moduleType],
              customColor: color,
            },
          },
        }))
      },
      
      getStats: (moduleType) => {
        return get().stats[moduleType] || defaultStats
      },
      
      getSortedModules: (modules) => {
        const { stats } = get()
        
        return [...modules].sort((a, b) => {
          const statsA = stats[a] || defaultStats
          const statsB = stats[b] || defaultStats
          
          // 1. 收藏的排在前面
          if (statsA.isFavorite !== statsB.isFavorite) {
            return statsA.isFavorite ? -1 : 1
          }
          
          // 2. 使用次数多的排在前面
          if (statsA.usageCount !== statsB.usageCount) {
            return statsB.usageCount - statsA.usageCount
          }
          
          // 3. 最近使用的排在前面
          return statsB.lastUsed - statsA.lastUsed
        })
      },

      getQuickList: (allowed, limit = QUICK_LIST_LIMIT) => {
        const allow = allowed ? new Set<string>(allowed) : null
        const used = Object.entries(get().stats)
          .filter(([type, st]) => st && typeof st === 'object' && type !== 'custom_module' && (!allow || allow.has(type)))
          .map(([type, st]) => ({ type, count: num(st?.usageCount), last: num(st?.lastUsed) }))
          .filter((m) => m.count > 0 || m.last > 0)
        // 综合名次 = 最近使用名次 + 使用频次名次，越小越靠前；并列时更近使用者在前
        const byRecent = [...used].sort((a, b) => b.last - a.last)
        const byCount = [...used].sort((a, b) => b.count - a.count)
        const score = (m: { type: string }) => byRecent.findIndex((x) => x.type === m.type) + byCount.findIndex((x) => x.type === m.type)
        return used
          .map((m) => ({ ...m, score: score(m) }))
          .sort((a, b) => a.score - b.score || b.last - a.last)
          .slice(0, limit)
          .map((m) => m.type as ModuleType)
      },
    }),
    {
      name: 'module-stats-storage',
      // 旧数据或损坏数据：stats 不是对象时回退为空，其余字段保留
      merge: (persisted, current) => {
        const stats = (persisted as { stats?: unknown } | null)?.stats
        const ok = stats && typeof stats === 'object' && !Array.isArray(stats)
        return { ...current, stats: ok ? (stats as ModuleStatsStore['stats']) : current.stats }
      },
    }
  )
)
