import { create } from 'zustand'

interface DataSelectionState {
  /** Reference text of the data row picked in the data sidebar; nodes that use it are highlighted. */
  selectedReference: string | null
  toggle(reference: string): void
  clear(): void
}

export const useDataSelectionStore = create<DataSelectionState>(set => ({
  selectedReference: null,
  toggle: reference => set(state => ({ selectedReference: state.selectedReference === reference ? null : reference })),
  clear: () => set({ selectedReference: null }),
}))
