// Source: WebRPA@5ccb900e, store/layoutStore.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * WebRPA 编辑器 面板布局 Store
 *
 * 持久化用户对左/右/底栏的拖拽尺寸偏好到 localStorage（不写项目目录）。
 * 设计原则：尺寸更新走单 store 字段，避免引发整个工作流的重渲染。
 */
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface LayoutState {
  /** 左侧模块面板宽度（px），用户拖拽改变 */
  leftWidth: number
  /** 右侧配置面板宽度（px），用户拖拽改变 */
  rightWidth: number
  /** 底部日志/数据面板高度（px），用户拖拽改变 */
  bottomHeight: number
  /** 小助手抽屉宽度（px），用户拖拽改变 */
  aiAssistantWidth: number
  /** 编辑器视图模式：流程图 / 模块条（影刀式线性） */
  editorViewMode: 'flow' | 'block'

  setLeftWidth: (w: number) => void
  setRightWidth: (w: number) => void
  setBottomHeight: (h: number) => void
  setAiAssistantWidth: (w: number) => void
  setEditorViewMode: (m: 'flow' | 'block') => void
  resetLayout: () => void
}

const DEFAULTS = {
  leftWidth: 256,    // w-64
  rightWidth: 320,   // w-80
  bottomHeight: 256, // h-64
  aiAssistantWidth: 440,
}

const LIMITS = {
  left: { min: 180, max: 560 },
  right: { min: 240, max: 720 },
  bottom: { min: 120, max: 720 },
  aiAssistant: { min: 320, max: 900 },
}

const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v))

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      leftWidth: DEFAULTS.leftWidth,
      rightWidth: DEFAULTS.rightWidth,
      bottomHeight: DEFAULTS.bottomHeight,
      aiAssistantWidth: DEFAULTS.aiAssistantWidth,
      editorViewMode: 'flow',
      setLeftWidth: (w) => set({ leftWidth: clamp(w, LIMITS.left.min, LIMITS.left.max) }),
      setRightWidth: (w) => set({ rightWidth: clamp(w, LIMITS.right.min, LIMITS.right.max) }),
      setBottomHeight: (h) => set({ bottomHeight: clamp(h, LIMITS.bottom.min, LIMITS.bottom.max) }),
      setAiAssistantWidth: (w) => set({ aiAssistantWidth: clamp(w, LIMITS.aiAssistant.min, LIMITS.aiAssistant.max) }),
      setEditorViewMode: (m) => set({ editorViewMode: m }),
      resetLayout: () => set({ ...DEFAULTS }),
    }),
    {
      name: 'autoflow.studio.mock.editor.layout',
      storage: createJSONStorage(() => localStorage),
      version: 1,
    },
  ),
)

export const LAYOUT_LIMITS = LIMITS
