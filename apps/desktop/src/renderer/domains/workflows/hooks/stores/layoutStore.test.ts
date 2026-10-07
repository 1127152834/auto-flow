import { beforeEach, describe, expect, it } from 'vitest'
import { LAYOUT_DEFAULTS, LAYOUT_LIMITS, useLayoutStore } from './layoutStore'

const NAME = 'autoflow.studio.mock.editor.layout'

beforeEach(() => {
  localStorage.clear()
  useLayoutStore.getState().resetLayout()
})

describe('layoutStore', () => {
  it('新字段默认保持旧行为', () => {
    const s = useLayoutStore.getState()
    expect(s.leftCollapsed).toBe(false)
    expect(s.bottomMode).toBe('expanded')
  })

  it('从 version 1 的持久数据迁移时保留用户宽度', async () => {
    localStorage.setItem(NAME, JSON.stringify({
      version: 1,
      state: { leftWidth: 300, rightWidth: 410, bottomHeight: 180, aiAssistantWidth: 500, editorViewMode: 'block' },
    }))
    await useLayoutStore.persist.rehydrate()
    const s = useLayoutStore.getState()
    expect([s.leftWidth, s.rightWidth, s.bottomHeight, s.aiAssistantWidth]).toEqual([300, 410, 180, 500])
    expect(s.editorViewMode).toBe('block')
    expect(s.leftCollapsed).toBe(false)
    expect(s.bottomMode).toBe('expanded')
  })

  it('version 2 的折叠与底部模式可持久读回', async () => {
    localStorage.setItem(NAME, JSON.stringify({
      version: 2,
      state: { leftWidth: 256, leftCollapsed: true, bottomMode: 'status' },
    }))
    await useLayoutStore.persist.rehydrate()
    expect(useLayoutStore.getState().leftCollapsed).toBe(true)
    expect(useLayoutStore.getState().bottomMode).toBe('status')
  })

  it('setter 写入并持久化为 version 2', () => {
    useLayoutStore.getState().setLeftCollapsed(true)
    useLayoutStore.getState().setBottomMode('status')
    const saved = JSON.parse(localStorage.getItem(NAME)!)
    expect(saved.version).toBe(2)
    expect(saved.state.leftCollapsed).toBe(true)
    expect(saved.state.bottomMode).toBe('status')
  })

  it('宽度仍按 LAYOUT_LIMITS 夹取', () => {
    useLayoutStore.getState().setLeftWidth(9999)
    expect(useLayoutStore.getState().leftWidth).toBe(LAYOUT_LIMITS.left.max)
  })

  it('resetLayout 恢复默认宽度与新字段', () => {
    const s = useLayoutStore.getState()
    s.setLeftWidth(400)
    s.setLeftCollapsed(true)
    s.setBottomMode('status')
    useLayoutStore.getState().resetLayout()
    const r = useLayoutStore.getState()
    expect(r.leftWidth).toBe(LAYOUT_DEFAULTS.leftWidth)
    expect(r.leftCollapsed).toBe(false)
    expect(r.bottomMode).toBe('expanded')
  })
})
