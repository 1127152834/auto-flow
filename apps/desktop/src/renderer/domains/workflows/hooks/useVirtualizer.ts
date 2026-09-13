// Source: WebRPA@5ccb900e, hooks/useVirtualizer.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 极简手写虚拟滚动 hook（不依赖第三方库）。
 * 适用场景：固定/估算行高的长列表，10k+ 行依然 60fps。
 *
 * 用法：
 *   const ref = useRef<HTMLDivElement>(null)
 *   const { virtualItems, totalSize } = useVirtualizer({
 *     count: items.length,
 *     getScrollElement: () => ref.current,
 *     estimateSize: 28,
 *     overscan: 8,
 *   })
 *
 *   <div ref={ref} className="overflow-auto h-full">
 *     <div style={{ height: totalSize, position: 'relative' }}>
 *       {virtualItems.map(v => (
 *         <div key={v.index} style={{ position:'absolute', top: v.start, left:0, right:0 }}>
 *           {items[v.index]}
 *         </div>
 *       ))}
 *     </div>
 *   </div>
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

export interface VirtualItem {
  index: number
  start: number
  size: number
}

export interface UseVirtualizerOptions {
  count: number
  getScrollElement: () => HTMLElement | null
  estimateSize: number
  overscan?: number
}

export function useVirtualizer({
  count,
  getScrollElement,
  estimateSize,
  overscan = 6,
}: UseVirtualizerOptions) {
  const [scrollTop, setScrollTop] = useState(0)
  const [viewportHeight, setViewportHeight] = useState(0)
  const rafRef = useRef<number | null>(null)

  useLayoutEffect(() => {
    const el = getScrollElement()
    if (!el) return

    const updateMetrics = () => {
      setScrollTop(el.scrollTop)
      setViewportHeight(el.clientHeight)
    }

    updateMetrics()

    const handleScroll = () => {
      if (rafRef.current !== null) return
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null
        setScrollTop(el.scrollTop)
      })
    }

    el.addEventListener('scroll', handleScroll, { passive: true })

    const ro = new ResizeObserver(() => updateMetrics())
    ro.observe(el)

    return () => {
      el.removeEventListener('scroll', handleScroll)
      ro.disconnect()
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [getScrollElement])

  const totalSize = count * estimateSize

  // count 变化时（如切换展示条数）重新校准滚动位置：
  // 行数变少而容器已向下滚动时，浏览器会自动夹取 DOM 的 scrollTop，
  // 但 React 中的 scrollTop 状态仍是旧的大值，会导致可视窗口算空、表格看似“没刷新”。
  // 这里在每次 count 变化后同步真实滚动位置，确保改动立即可见。
  useLayoutEffect(() => {
    const el = getScrollElement()
    if (!el) return
    if (el.scrollTop !== scrollTop) setScrollTop(el.scrollTop)

  }, [count, getScrollElement])

  // 渲染时再按当前总高度夹取一次，双保险：即使状态滞后也不会出现空白窗口
  const maxScroll = Math.max(0, totalSize - viewportHeight)
  const clampedScrollTop = Math.min(Math.max(0, scrollTop), maxScroll)

  const visibleCount = Math.max(1, Math.ceil(viewportHeight / estimateSize) + overscan * 2)
  const startIndex = Math.max(0, Math.floor(clampedScrollTop / estimateSize) - overscan)
  const endIndex = Math.min(count, startIndex + visibleCount)

  const virtualItems: VirtualItem[] = []
  for (let i = startIndex; i < endIndex; i++) {
    virtualItems.push({
      index: i,
      start: i * estimateSize,
      size: estimateSize,
    })
  }

  /** 滚动到底部（写直接修改，比 scrollIntoView 快） */
  const scrollToBottom = () => {
    const el = getScrollElement()
    if (!el) return
    el.scrollTop = el.scrollHeight
  }

  /** 滚动到顶部 */
  const scrollToTop = () => {
    const el = getScrollElement()
    if (!el) return
    el.scrollTop = 0
  }

  return {
    virtualItems,
    totalSize,
    scrollToBottom,
    scrollToTop,
  }
}

/** 节流：每 N 毫秒最多触发一次回调，但首次和末次都会执行 */
export function throttle<T extends (...args: any[]) => void>(fn: T, ms: number): T {
  let last = 0
  let timer: ReturnType<typeof setTimeout> | null = null
  let lastArgs: any[] | null = null
  const wrapped = (...args: any[]) => {
    const now = Date.now()
    const remaining = ms - (now - last)
    lastArgs = args
    if (remaining <= 0) {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      last = now
      fn(...args)
      lastArgs = null
    } else if (!timer) {
      timer = setTimeout(() => {
        last = Date.now()
        timer = null
        if (lastArgs) {
          fn(...lastArgs)
          lastArgs = null
        }
      }, remaining)
    }
  }
  return wrapped as T
}

// useEffect 占位（防止 lint 标记 unused import）
void useEffect
