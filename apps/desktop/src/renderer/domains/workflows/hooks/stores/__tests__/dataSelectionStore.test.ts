import { beforeEach, describe, expect, it } from 'vitest'
import { useDataSelectionStore } from '../dataSelectionStore'

const state = () => useDataSelectionStore.getState()

describe('dataSelectionStore', () => {
  beforeEach(() => state().clear())

  it('点击选中，再次点击同一项取消，点另一项则切换', () => {
    state().toggle('{input.a.b}')
    expect(state().selectedReference).toBe('{input.a.b}')
    state().toggle('{input.a.c}')
    expect(state().selectedReference).toBe('{input.a.c}')
    state().toggle('{input.a.c}')
    expect(state().selectedReference).toBeNull()
  })

  it('clear 取消选中', () => {
    state().toggle('{x}')
    state().clear()
    expect(state().selectedReference).toBeNull()
  })
})
