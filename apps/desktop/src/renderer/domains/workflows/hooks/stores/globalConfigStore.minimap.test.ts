import { beforeEach, describe, expect, it } from 'vitest'
import { resolveMinimapVisible, useGlobalConfigStore } from './globalConfigStore'

const NAME = 'autoflow-studio-mock-global-config'

beforeEach(() => {
  localStorage.clear()
  useGlobalConfigStore.getState().resetConfig()
})

describe('小地图默认值', () => {
  it('新装：新布局下默认关闭，旧布局下保持开启', () => {
    const c = useGlobalConfigStore.getState().config
    expect(resolveMinimapVisible(c, true)).toBe(false)
    expect(resolveMinimapVisible(c, false)).toBe(true)
  })

  it('用户显式切换后，新布局按用户值', () => {
    const s = useGlobalConfigStore.getState()
    s.updateSystemConfig({ canvasWidgets: { ...s.config.system.canvasWidgets, minimap: false } })
    s.updateSystemConfig({ canvasWidgets: { ...useGlobalConfigStore.getState().config.system.canvasWidgets, minimap: true } })
    expect(resolveMinimapVisible(useGlobalConfigStore.getState().config, true)).toBe(true)
  })

  it('改其它小组件不算显式设置小地图', () => {
    const s = useGlobalConfigStore.getState()
    s.updateSystemConfig({ canvasWidgets: { ...s.config.system.canvasWidgets, controls: false } })
    expect(resolveMinimapVisible(useGlobalConfigStore.getState().config, true)).toBe(false)
  })

  it('迁移：旧版数据里 minimap=true 视为默认值，新布局下关闭', async () => {
    localStorage.setItem(NAME, JSON.stringify({ version: 0, state: { config: { system: { canvasWidgets: { minimap: true, controls: false } } } } }))
    await useGlobalConfigStore.persist.rehydrate()
    const c = useGlobalConfigStore.getState().config
    expect(c.system.canvasWidgets.controls).toBe(false)
    expect(resolveMinimapVisible(c, true)).toBe(false)
  })

  it('迁移：旧版数据里 minimap=false 视为用户选择，保持关闭且标为显式', async () => {
    localStorage.setItem(NAME, JSON.stringify({ version: 0, state: { config: { system: { canvasWidgets: { minimap: false } } } } }))
    await useGlobalConfigStore.persist.rehydrate()
    const c = useGlobalConfigStore.getState().config
    expect(c.system.minimapExplicit).toBe(true)
    expect(resolveMinimapVisible(c, true)).toBe(false)
    expect(resolveMinimapVisible(c, false)).toBe(false)
  })

  it('新版数据里显式设置过 minimap=true，刷新后保持开启', async () => {
    localStorage.setItem(NAME, JSON.stringify({ version: 1, state: { config: { system: { minimapExplicit: true, canvasWidgets: { minimap: true } } } } }))
    await useGlobalConfigStore.persist.rehydrate()
    expect(resolveMinimapVisible(useGlobalConfigStore.getState().config, true)).toBe(true)
  })
})
