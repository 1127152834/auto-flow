// Source: WebRPA@5ccb900e, store/debugStore.ts; see SOURCE.md for license and adaptation boundaries.
import { create } from 'zustand'
import {isDebugPauseContext, type DebugPauseContext} from '../../lib/debugControlContract'

/**
 * 可视化调试状态：断点集合 + 暂停态。
 * 断点是"画布编辑态"数据（持久跟随节点）；暂停态是"运行态"数据。
 */
interface DebugState {
  breakpoints: Set<string>
  stepMode: boolean            // 是否以单步模式启动下次运行
  pauseContext: DebugPauseContext | null
  pauseRevision: number         // Local UI generation; never substitutes for a server pause identity.
  isPaused: boolean
  pausedNodeId: string | null
  pausedLabel: string | null
  pausedVariables: Record<string, any>
  pausedReason: 'breakpoint' | 'step' | null

  toggleBreakpoint: (nodeId: string) => void
  clearBreakpoints: () => void
  hasBreakpoint: (nodeId: string) => boolean
  setStepMode: (v: boolean) => void

  setPaused: (info: { pauseId?:string; controlRevision?:number; nodeId: string; label?: string; variables?: Record<string, any>; reason?: 'breakpoint' | 'step' }) => void
  clearPaused: () => void
}

export const useDebugStore = create<DebugState>((set, get) => ({
  breakpoints: new Set<string>(),
  stepMode: false,
  pauseContext:null,
  pauseRevision: 0,
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

  setPaused: (info) => set((state) => {
    const pauseContext=isDebugPauseContext(info)?{pauseId:info.pauseId,controlRevision:info.controlRevision}:null
    if(state.isPaused && pauseContext && state.pauseContext?.pauseId===pauseContext.pauseId && state.pauseContext.controlRevision===pauseContext.controlRevision)return state
    return {
      pauseContext,
      pauseRevision:state.pauseRevision+1,
      isPaused:true,
      pausedNodeId:info.nodeId,
      pausedLabel:info.label || info.nodeId,
      pausedVariables:info.variables || {},
      pausedReason:info.reason || 'breakpoint',
    }
  }),
  clearPaused: () => set({ isPaused: false, pauseContext:null, pausedNodeId: null, pausedLabel: null, pausedReason: null }),
}))
