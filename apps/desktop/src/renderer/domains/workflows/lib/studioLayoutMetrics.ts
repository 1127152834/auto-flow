import { LAYOUT_DEFAULTS } from '../hooks/stores/layoutStore'

/** 新布局规格：工具栏单行高度（px） */
export const TOOLBAR_HEIGHT = 48
/** 新布局规格：底部状态条高度（px） */
export const STATUS_BAR_HEIGHT = 28
/** 新布局规格：运行时底部面板占窗口高度的比例 */
export const RUNNING_BOTTOM_RATIO = 0.3
/** 验收：默认窗口（1440x900）空闲态画布占比下限 */
export const MIN_CANVAS_RATIO_DEFAULT = 0.6
/** 验收：小窗口（1280x800）左右折叠时画布占比下限 */
export const MIN_CANVAS_RATIO_COLLAPSED = 0.5

export interface CanvasAreaInput {
  windowWidth: number
  windowHeight: number
  toolbarHeight?: number
  leftWidth?: number
  leftCollapsed: boolean
  rightWidth?: number
  rightVisible: boolean
  bottomMode: 'status' | 'expanded'
  bottomHeight?: number
  statusBarHeight?: number
  runningBottomRatio?: number
  /** 运行中：底部面板按 runningBottomRatio 展开 */
  running?: boolean
}

/** 画布面积 / 窗口面积（纯函数，供测试与 Electron 实测对照） */
export function canvasAreaRatio(i: CanvasAreaInput): number {
  if (!(i.windowWidth > 0) || !(i.windowHeight > 0)) return 0
  const left = i.leftCollapsed ? 0 : (i.leftWidth ?? LAYOUT_DEFAULTS.leftWidth)
  const right = i.rightVisible ? (i.rightWidth ?? LAYOUT_DEFAULTS.rightWidth) : 0
  const bottom = i.running
    ? i.windowHeight * (i.runningBottomRatio ?? RUNNING_BOTTOM_RATIO)
    : i.bottomMode === 'status'
      ? (i.statusBarHeight ?? STATUS_BAR_HEIGHT)
      : (i.bottomHeight ?? LAYOUT_DEFAULTS.bottomHeight)
  const width = Math.max(0, i.windowWidth - left - right)
  const height = Math.max(0, i.windowHeight - (i.toolbarHeight ?? TOOLBAR_HEIGHT) - bottom)
  return (width * height) / (i.windowWidth * i.windowHeight)
}
