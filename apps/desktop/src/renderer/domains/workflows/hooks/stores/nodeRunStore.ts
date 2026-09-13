// Source: WebRPA@5ccb900e, store/nodeRunStore.ts; see SOURCE.md for license and adaptation boundaries.
import { create } from 'zustand'

/** 节点运行态：用于执行过程中在流程图/模块条上实时高亮 */
export type NodeRunStatus = 'running' | 'success' | 'failed'

interface NodeRunState {
  /** nodeId -> 运行态 */
  statuses: Record<string, NodeRunStatus>
  setStatus: (nodeId: string, status: NodeRunStatus) => void
  clear: () => void
}

export const useNodeRunStore = create<NodeRunState>((set) => ({
  statuses: {},
  setStatus: (nodeId, status) =>
    set((s) => ({ statuses: { ...s.statuses, [nodeId]: status } })),
  clear: () => set({ statuses: {} }),
}))
