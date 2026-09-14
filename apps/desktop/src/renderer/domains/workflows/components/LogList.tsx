// Source: WebRPA@5ccb900e, components/workflow/LogList.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 高性能日志列表 - 虚拟滚动 60fps
 * 视觉：左侧色条状态指示 + 时间戳 + 级别徽章 + 高亮搜索
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { cn } from '../lib/utils'
import { useVirtualizer } from '../hooks/useVirtualizer'
import type { LogEntry, LogLevel } from '../types/index'

const ROW_HEIGHT = 26

const levelStyles: Record<
  LogLevel,
  { bar: string; text: string; tagBg: string; tagText: string }
> = {
  debug:   { bar: 'bg-[hsl(var(--slate-400))]',   text: 'text-[hsl(var(--slate-600))]',   tagBg: 'bg-[hsl(var(--slate-100))]',   tagText: 'text-[hsl(var(--slate-700))]' },
  info:    { bar: 'bg-[hsl(var(--info-500))]',    text: 'text-[hsl(var(--info-700))]',    tagBg: 'bg-[hsl(var(--info-50))]',    tagText: 'text-[hsl(var(--info-700))]' },
  success: { bar: 'bg-[hsl(var(--success-500))]', text: 'text-[hsl(var(--success-700))]', tagBg: 'bg-[hsl(var(--success-50))]', tagText: 'text-[hsl(var(--success-700))]' },
  warning: { bar: 'bg-[hsl(var(--warning-500))]', text: 'text-[hsl(var(--warning-700))]', tagBg: 'bg-[hsl(var(--warning-50))]', tagText: 'text-[hsl(var(--warning-700))]' },
  error:   { bar: 'bg-[hsl(var(--danger-500))]',  text: 'text-[hsl(var(--danger-700))]',  tagBg: 'bg-[hsl(var(--danger-50))]',  tagText: 'text-[hsl(var(--danger-700))]' },
}

interface LogListProps {
  logs: LogEntry[]
  searchQuery?: string
  onLogClick?: (nodeId?: string) => void
}

function highlightText(text: string, query: string) {
  if (!query) return text
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx < 0) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-[hsl(var(--warning-100))] text-[hsl(var(--warning-700))] rounded px-1 font-semibold">
        {text.slice(idx, idx + query.length)}
      </mark>
      {text.slice(idx + query.length)}
    </>
  )
}

export function LogList({ logs, searchQuery, onLogClick }: LogListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const getScrollElement = useCallback(() => scrollRef.current, [])
  const [autoScroll, setAutoScroll] = useState(true)
  const lastLogCountRef = useRef(logs.length)

  const { virtualItems, totalSize, scrollToBottom } = useVirtualizer({
    count: logs.length,
    getScrollElement,
    estimateSize: ROW_HEIGHT,
    overscan: 10,
  })

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const handler = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20
      setAutoScroll(nearBottom)
    }
    el.addEventListener('scroll', handler, { passive: true })
    return () => el.removeEventListener('scroll', handler)
  }, [])

  useEffect(() => {
    if (logs.length !== lastLogCountRef.current) {
      lastLogCountRef.current = logs.length
      if (autoScroll) {
        requestAnimationFrame(() => scrollToBottom())
      }
    }
  }, [logs.length, autoScroll, scrollToBottom])

  return (
    <div ref={scrollRef} className="flex-1 overflow-auto px-2 py-1.5">
      <div style={{ height: totalSize, position: 'relative' }}>
        {virtualItems.map((v) => {
          const log = logs[v.index]
          if (!log) return null
          const style = levelStyles[log.level]
          const ts = (() => {
            try {
              return new Date(log.timestamp).toLocaleTimeString()
            } catch {
              return log.timestamp
            }
          })()
          return (
            <div
              key={log.id}
              style={{
                position: 'absolute',
                top: v.start,
                left: 0,
                right: 0,
                height: ROW_HEIGHT,
              }}
              className={cn(
                'text-[12px] font-mono pl-3 pr-3 leading-[26px] truncate rounded-control flex items-center gap-2 transition-colors duration-100 group',
                log.nodeId
                  ? 'cursor-pointer hover:bg-[hsl(var(--brand-50))] hover:shadow-xs'
                  : 'hover:bg-[hsl(var(--slate-100)/0.6)]'
              )}
              onClick={() => onLogClick?.(log.nodeId)}
              title={log.nodeId ? '点击定位到对应模块' : log.message}
            >
              {/* 左侧状态色条 */}
              <span className={cn('w-[3px] h-3.5 rounded-full shrink-0 transition-all', style.bar, 'group-hover:h-4')} />
              {/* 时间戳 */}
              <span className="text-[10.5px] text-[hsl(var(--muted-foreground))] tabular-nums shrink-0">
                {ts}
              </span>
              {/* 级别徽章 */}
              <span
                className={cn(
                  'shrink-0 px-1.5 py-0 text-[9.5px] font-bold uppercase tracking-wider rounded',
                  style.tagBg,
                  style.tagText
                )}
              >
                {log.level}
              </span>
              {/* 消息 */}
              <span className={cn('flex-1 truncate', style.text)}>
                {highlightText(log.message, searchQuery || '')}
              </span>
              {/* 耗时 */}
              {log.duration !== undefined && log.duration !== null && (
                <span className="shrink-0 text-[10.5px] text-[hsl(var(--brand-600))] font-semibold tabular-nums px-1.5 py-0 rounded bg-[hsl(var(--brand-50))] border border-[hsl(var(--brand-500)/0.2)]">
                  {log.duration.toFixed(2)}ms
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
