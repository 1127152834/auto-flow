// Source: WebRPA@5ccb900e, store/aiActionLogStore.ts; see SOURCE.md for license and adaptation boundaries.
import { create } from 'zustand'
import type { Node, Edge } from '@xyflow/react'
import type { NodeData } from '../../editor-store'

/** AI 会话操作时间线：记录小助手每次「会改动画布」的操作，并保存操作前快照，支持一键回退。 */
export interface AiActionEntry {
  id: string
  ts: number
  action: string          // client_action 名称
  label: string           // 中文可读标签
  /** 操作「之前」的画布快照，用于一键回退到这一步之前 */
  before: {
    nodes: Node<NodeData>[]
    edges: Edge[]
    name: string
  }
}

interface AiActionLogState {
  entries: AiActionEntry[]
  record: (entry: AiActionEntry) => void
  clear: () => void
}

const MAX_ENTRIES = 100

export const useAiActionLogStore = create<AiActionLogState>((set) => ({
  entries: [],
  record: (entry) =>
    set((s) => {
      const next = [...s.entries, entry]
      if (next.length > MAX_ENTRIES) next.splice(0, next.length - MAX_ENTRIES)
      return { entries: next }
    }),
  clear: () => set({ entries: [] }),
}))
