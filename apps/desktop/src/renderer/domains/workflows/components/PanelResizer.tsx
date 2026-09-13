// Source: WebRPA@5ccb900e, components/workflow/PanelResizer.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 面板边缘拖拽手柄
 *
 * 设计目标：高频拖拽时不让 React 重渲染整棵组件树。
 * 实现：
 * - mousedown 时只在文档级监听 mousemove/mouseup
 * - 用 requestAnimationFrame 合并 mousemove 事件，避免 60+ fps 反复 setState
 * - 拖拽中给 body 加 cursor 样式 + user-select: none，防止误选文本
 * - 释放时一次性同步进 store（store 本身只占一个数字字段，订阅它的组件最多重渲染一次）
 */
import { useCallback, useEffect, useRef } from 'react'

type Direction = 'horizontal' | 'vertical'
type Side = 'left' | 'right' | 'top' | 'bottom'

interface PanelResizerProps {
  direction: Direction
  /** resizer 贴在容器哪条边 */
  side: Side
  /** 当前尺寸 */
  size: number
  /** 可选最小最大尺寸 */
  minSize?: number
  maxSize?: number
  /** 拖拽时实时回调（用于即时更新 UI；store 提交在 onCommit） */
  onLive?: (next: number) => void
  /** 用户松手时提交一次 */
  onCommit: (next: number) => void
  /**
   * 拖拽方向修正：
   * - 左侧栏右边缘：向右拖宽度变大（factor = 1）
   * - 右侧栏左边缘：向右拖宽度变小（factor = -1）
   * - 底部栏上边缘：向上拖高度变大（factor = -1）
   */
  factor?: 1 | -1
  className?: string
}

export function PanelResizer({
  direction,
  side,
  size,
  minSize = 0,
  maxSize = 9999,
  onLive,
  onCommit,
  factor = 1,
  className = '',
}: PanelResizerProps) {
  const startRef = useRef({ pos: 0, size: 0, raf: 0, lastNext: 0 })

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      startRef.current.pos = direction === 'horizontal' ? e.clientX : e.clientY
      startRef.current.size = size
      startRef.current.lastNext = size

      const isH = direction === 'horizontal'
      document.body.style.cursor = isH ? 'col-resize' : 'row-resize'
      document.body.style.userSelect = 'none'
      // 防止 iframe / canvas 抢走指针事件
      document.body.style.pointerEvents = 'none'
      document.documentElement.style.pointerEvents = 'auto'

      const onMove = (ev: MouseEvent) => {
        ev.preventDefault()
        const cur = isH ? ev.clientX : ev.clientY
        const delta = (cur - startRef.current.pos) * factor
        const next = Math.max(minSize, Math.min(maxSize, startRef.current.size + delta))
        startRef.current.lastNext = next
        // 用 RAF 合并多次 mousemove
        if (!startRef.current.raf) {
          startRef.current.raf = requestAnimationFrame(() => {
            startRef.current.raf = 0
            onLive?.(startRef.current.lastNext)
          })
        }
      }

      const onUp = () => {
        document.removeEventListener('mousemove', onMove, true)
        document.removeEventListener('mouseup', onUp, true)
        if (startRef.current.raf) {
          cancelAnimationFrame(startRef.current.raf)
          startRef.current.raf = 0
        }
        document.body.style.cursor = ''
        document.body.style.userSelect = ''
        document.body.style.pointerEvents = ''
        document.documentElement.style.pointerEvents = ''
        onCommit(startRef.current.lastNext)
      }

      document.addEventListener('mousemove', onMove, true)
      document.addEventListener('mouseup', onUp, true)
    },
    [direction, size, minSize, maxSize, factor, onLive, onCommit],
  )

  useEffect(() => () => {
    if (startRef.current.raf) cancelAnimationFrame(startRef.current.raf)
  }, [])

  const isH = direction === 'horizontal'
  const baseStyle: React.CSSProperties = isH
    ? {
        position: 'absolute',
        top: 0,
        bottom: 0,
        ...(side === 'right' ? { right: -3 } : { left: -3 }),
        width: 6,
        cursor: 'col-resize',
        zIndex: 30,
      }
    : {
        position: 'absolute',
        left: 0,
        right: 0,
        ...(side === 'top' ? { top: -3 } : { bottom: -3 }),
        height: 6,
        cursor: 'row-resize',
        zIndex: 30,
      }

  return (
    <div
      className={`panel-resizer ${className}`}
      style={baseStyle}
      onMouseDown={handleMouseDown}
      role="separator"
      aria-orientation={isH ? 'vertical' : 'horizontal'}
    />
  )
}
