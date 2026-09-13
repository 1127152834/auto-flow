// Source: WebRPA@5ccb900e, store/debugStore.ts; see SOURCE.md for license and adaptation boundaries.
import { create } from 'zustand'

/**
 * 可视化调试状态：断点集合 + 暂停态。
 * 断点是"画布编辑态"数据（持久跟随节点）；暂停态是"运行态"数据。
 */
interface DebugState {
  breakpoints: Set<string>
  stepMode: boolean            // 是否以单步模式启动下次运行
  isPaused: boolean
  pausedNodeId: string | null
  pausedLabel: string | null
  pausedVariables: Record<string, any>
  pausedReason: 'breakpoint' | 'step' | null

  toggleBreakpoint: (nodeId: string) => void
  clearBreakpoints: () => void
  hasBreakpoint: (nodeId: string) => boolean
  setStepMode: (v: boolean) => void

  setPaused: (info: { nodeId: string; label?: string; variables?: Record<string, any>; reason?: 'breakpoint' | 'step' }) => void
  clearPaused: () => void
}

export const useDebugStore = create<DebugState>((set, get) => ({
  breakpoints: new Set<string>(),
  stepMode: false,
  isPaused: false,
  pausedNodeId: null,
  pausedLabel: null,
  pausedVariables: {},
  pausedReason: null,

  toggleBreakpoint: (nodeId) => set((s) => {
    const next = new Set(s.breakpoints)
    if (next.has(nodeId)) next.delete(nodeId); else next.add(nodeId)
    return { breakpoints: next }
  }),
  clearBreakpoints: () => set({ breakpoints: new Set<string>() }),
  hasBreakpoint: (nodeId) => get().breakpoints.has(nodeId),
  setStepMode: (v) => set({ stepMode: v }),

  setPaused: (info) => set({
    isPaused: true,
    pausedNodeId: info.nodeId,
    pausedLabel: info.label || info.nodeId,
    pausedVariables: info.variables || {},
    pausedReason: info.reason || 'breakpoint',
  }),
  clearPaused: () => set({ isPaused: false, pausedNodeId: null, pausedLabel: null, pausedReason: null }),
}))
