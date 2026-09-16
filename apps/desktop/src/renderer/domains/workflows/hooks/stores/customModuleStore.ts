// Source: WebRPA@5ccb900e, store/customModuleStore.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 自定义模块状态管理
 */
import { create } from 'zustand'
import { customModulesApi } from '../../api'
import type { CustomModule } from '../../types/customModule'

interface CustomModuleState {
  modules: CustomModule[]
  isLoading: boolean
  error: string | null
  selectedModule: CustomModule | null
  
  // 操作
  loadModules: (params?: { category?: string; search?: string }) => Promise<void>
  getModule: (id: string) => Promise<CustomModule | null>
  createModule: (data: any) => Promise<CustomModule | null>
  updateModule: (id: string, data: any, expectedRevision?: number) => Promise<CustomModule | null>
  deleteModule: (id: string, expectedRevision?: number) => Promise<boolean>
  duplicateModule: (id: string, newName?: string) => Promise<CustomModule | null>
  importModule: (data: any) => Promise<CustomModule | null>
  setSelectedModule: (module: CustomModule | null) => void
}

export const useCustomModuleStore = create<CustomModuleState>((set, get) => ({
  modules: [],
  isLoading: false,
  error: null,
  selectedModule: null,
  
  loadModules: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const result = await customModulesApi.list(params)
      if (result.data) {
        set({ modules: result.data.modules, isLoading: false })
      } else {
        set({ error: result.error || '加载失败', isLoading: false })
      }
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },
  
  getModule: async (id) => {
    try {
      const result = await customModulesApi.get(id)
      if (result.data) {
        return result.data
      }
      return null
    } catch (error) {
      console.error('获取模块失败:', error)
      return null
    }
  },
  
  createModule: async (data) => {
    set({ isLoading: true, error: null })
    try {
      const result = await customModulesApi.create(data)
      if (result.data) {
        set(state => ({
          modules: [result.data, ...state.modules],
          isLoading: false
        }))
        return result.data
      } else {
        set({ error: result.error || '创建失败', isLoading: false })
        return null
      }
    } catch (error) {
      set({ error: String(error), isLoading: false })
      return null
    }
  },
  
  updateModule: async (id, data, expectedRevision) => {
    set({ isLoading: true, error: null })
    try {
      const revision = expectedRevision ?? get().modules.find(module => module.id === id)?.revision
      const result = await customModulesApi.update(id, data, revision)
      if (result.data) {
        set(state => ({
          modules: state.modules.map(m => m.id === id ? result.data : m),
          isLoading: false
        }))
        return result.data
      } else {
        set({ error: result.error || '更新失败', isLoading: false })
        return null
      }
    } catch (error) {
      set({ error: String(error), isLoading: false })
      return null
    }
  },
  
  deleteModule: async (id, expectedRevision) => {
    set({ isLoading: true, error: null })
    try {
      const revision = expectedRevision ?? get().modules.find(module => module.id === id)?.revision
      const result = await customModulesApi.delete(id, revision)
      if (result.data?.success) {
        set(state => ({
          modules: state.modules.filter(m => m.id !== id),
          isLoading: false
        }))
        return true
      } else {
        set({ error: result.error || '删除失败', isLoading: false })
        return false
      }
    } catch (error) {
      set({ error: String(error), isLoading: false })
      return false
    }
  },
  
  duplicateModule: async (id, newName) => {
    set({ isLoading: true, error: null })
    try {
      const result = await customModulesApi.duplicate(id, newName)
      if (result.data) {
        set(state => ({
          modules: [result.data, ...state.modules],
          isLoading: false
        }))
        return result.data
      } else {
        set({ error: result.error || '复制失败', isLoading: false })
        return null
      }
    } catch (error) {
      set({ error: String(error), isLoading: false })
      return null
    }
  },

  importModule: async (data) => {
    set({ isLoading: true, error: null })
    try {
      const result = await customModulesApi.importModule(data)
      if (result.data) {
        set(state => ({
          modules: [result.data, ...state.modules],
          isLoading: false,
        }))
        return result.data
      } else {
        set({ error: result.error || '导入失败', isLoading: false })
        return null
      }
    } catch (error) {
      set({ error: String(error), isLoading: false })
      return null
    }
  },
  
  setSelectedModule: (module) => {
    set({ selectedModule: module })
  }
}))
