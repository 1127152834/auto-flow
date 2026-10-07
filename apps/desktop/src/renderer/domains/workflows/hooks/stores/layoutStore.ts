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
  /** 左侧模块面板是否折叠（新布局；开关关闭时不被读取） */
  leftCollapsed: boolean
  /** 底部面板模式：状态条 / 展开（默认展开，保持旧行为） */
  bottomMode: 'status' | 'expanded'
  /** 用户是否手动选过底部模式；未选过时新布局按状态条显示 */
  bottomModeChosen: boolean

  setLeftWidth: (w: number) => void
  setRightWidth: (w: number) => void
  setBottomHeight: (h: number) => void
  setAiAssistantWidth: (w: number) => void
  setEditorViewMode: (m: 'flow' | 'block') => void
  setLeftCollapsed: (c: boolean) => void
  setBottomMode: (m: 'status' | 'expanded') => void
  resetLayout: () => void
}

const DEFAULTS = {
  leftWidth: 256,    // w-64
  rightWidth: 320,   // w-80
  bottomHeight: 256, // h-64
  aiAssistantWidth: 440,
  leftCollapsed: false,
  bottomMode: 'expanded' as 'status' | 'expanded',
  bottomModeChosen: false,
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
      leftCollapsed: DEFAULTS.leftCollapsed,
      bottomMode: DEFAULTS.bottomMode,
      bottomModeChosen: DEFAULTS.bottomModeChosen,
      setLeftWidth: (w) => set({ leftWidth: clamp(w, LIMITS.left.min, LIMITS.left.max) }),
      setRightWidth: (w) => set({ rightWidth: clamp(w, LIMITS.right.min, LIMITS.right.max) }),
      setBottomHeight: (h) => set({ bottomHeight: clamp(h, LIMITS.bottom.min, LIMITS.bottom.max) }),
      setAiAssistantWidth: (w) => set({ aiAssistantWidth: clamp(w, LIMITS.aiAssistant.min, LIMITS.aiAssistant.max) }),
      setEditorViewMode: (m) => set({ editorViewMode: m }),
      setLeftCollapsed: (c) => set({ leftCollapsed: c }),
      setBottomMode: (m) => set({ bottomMode: m, bottomModeChosen: true }),
      resetLayout: () => set({ ...DEFAULTS }),
    }),
    {
      name: 'autoflow.studio.mock.editor.layout',
      storage: createJSONStorage(() => localStorage),
      version: 2,
      // v1 -> v2：只补新字段，已有宽度原样保留（persist 随后与当前默认值浅合并）
      migrate: (persisted) => persisted as LayoutState,
    },
  ),
)

export const LAYOUT_LIMITS = LIMITS
export const LAYOUT_DEFAULTS = DEFAULTS
