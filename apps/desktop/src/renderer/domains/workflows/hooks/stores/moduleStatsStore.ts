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
}

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
    }),
    {
      name: 'module-stats-storage',
    }
  )
)
