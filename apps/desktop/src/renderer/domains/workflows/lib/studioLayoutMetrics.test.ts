import { describe, expect, it } from 'vitest'
import { LAYOUT_DEFAULTS } from '../hooks/stores/layoutStore'
import {
  MIN_CANVAS_RATIO_COLLAPSED, MIN_CANVAS_RATIO_DEFAULT, RUNNING_BOTTOM_RATIO,
  STATUS_BAR_HEIGHT, TOOLBAR_HEIGHT, canvasAreaRatio,
} from './studioLayoutMetrics'

const base = {
  leftWidth: LAYOUT_DEFAULTS.leftWidth,
  leftCollapsed: false,
  rightWidth: LAYOUT_DEFAULTS.rightWidth,
  rightVisible: false,
  bottomMode: 'status' as const,
  bottomHeight: LAYOUT_DEFAULTS.bottomHeight,
  toolbarHeight: TOOLBAR_HEIGHT,
  statusBarHeight: STATUS_BAR_HEIGHT,
  runningBottomRatio: RUNNING_BOTTOM_RATIO,
}

describe('canvasAreaRatio', () => {
  it('1440x900 空闲、未选中节点、右栏收起、底部状态条、左栏默认宽 >= 0.60', () => {
    const r = canvasAreaRatio({ ...base, windowWidth: 1440, windowHeight: 900 })
    expect(r).toBeGreaterThanOrEqual(MIN_CANVAS_RATIO_DEFAULT)
    expect(MIN_CANVAS_RATIO_DEFAULT).toBe(0.6)
  })

  it('1280x800 左右折叠 >= 0.50', () => {
    const r = canvasAreaRatio({ ...base, windowWidth: 1280, windowHeight: 800, leftCollapsed: true })
    expect(r).toBeGreaterThanOrEqual(MIN_CANVAS_RATIO_COLLAPSED)
    expect(MIN_CANVAS_RATIO_COLLAPSED).toBe(0.5)
  })

  it('当前旧布局（右栏展开 + 底部默认高度）低于 0.60，证明新布局是必要的', () => {
    const r = canvasAreaRatio({
      ...base, windowWidth: 1440, windowHeight: 900, rightVisible: true, bottomMode: 'expanded',
    })
    expect(r).toBeLessThan(MIN_CANVAS_RATIO_DEFAULT)
  })

  it('运行态底部按窗口高度占比计算，并随之缩小画布', () => {
    const idle = canvasAreaRatio({ ...base, windowWidth: 1440, windowHeight: 900 })
    const running = canvasAreaRatio({ ...base, windowWidth: 1440, windowHeight: 900, running: true })
    const expected = ((1440 - LAYOUT_DEFAULTS.leftWidth) * (900 - TOOLBAR_HEIGHT - 900 * RUNNING_BOTTOM_RATIO)) / (1440 * 900)
    expect(running).toBeCloseTo(expected, 10)
    expect(running).toBeLessThan(idle)
  })

  it('空间不足时不返回负数', () => {
    expect(canvasAreaRatio({ ...base, windowWidth: 100, windowHeight: 100, rightVisible: true })).toBe(0)
  })

  it('窗口尺寸为 0 或无效时返回 0，不产生 NaN', () => {
    expect(canvasAreaRatio({ ...base, windowWidth: 0, windowHeight: 900 })).toBe(0)
    expect(canvasAreaRatio({ ...base, windowWidth: 1440, windowHeight: 0 })).toBe(0)
    expect(canvasAreaRatio({ ...base, windowWidth: Number.NaN, windowHeight: 900 })).toBe(0)
  })
})
