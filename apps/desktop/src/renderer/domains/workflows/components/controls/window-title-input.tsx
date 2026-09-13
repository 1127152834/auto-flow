// Source: WebRPA@5ccb900e, components/ui/window-title-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { studioFetch } from '../../api/transport'
/**
 * 窗口标题输入框 - 带「可视化选择已打开窗口」按钮
 * 用于桌面应用自动化模块：用户可一键从当前打开的窗口列表中选择标题
 */
import { useState, useCallback, useRef, useEffect } from 'react'
import { MonitorSmartphone, Loader2, RefreshCw } from 'lucide-react'
import { VariableInput } from './variable-input'
import { getBackendBaseUrl } from '../../api/config'

interface WindowInfo {
  hwnd: number
  title: string
  class: string
}

interface WindowTitleInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export function WindowTitleInput({ value, onChange, placeholder }: WindowTitleInputProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [windows, setWindows] = useState<WindowInfo[]>([])
  const [error, setError] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  const fetchWindows = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await studioFetch(`${getBackendBaseUrl()}/api/desktop-picker/windows`)
      const data = await res.json()
      if (data.success) {
        setWindows(data.windows || [])
      } else {
        setError(data.error || '获取窗口列表失败')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const handleOpen = useCallback(() => {
    setOpen((v) => {
      const next = !v
      if (next) fetchWindows()
      return next
    })
  }, [fetchWindows])

  // 点击外部关闭
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div ref={containerRef} className="relative">
      <div className="flex gap-2">
        <VariableInput
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          className="flex-1"
        />
        <button
          type="button"
          onClick={handleOpen}
          title="从已打开的窗口中选择"
          className="flex items-center justify-center h-8 w-9 flex-shrink-0 rounded-[7px] border border-[hsl(var(--brand-500)/0.3)] bg-[hsl(var(--brand-50))] text-[hsl(var(--brand-600))] hover:bg-[hsl(var(--brand-100))] transition-colors"
        >
          <MonitorSmartphone className="w-4 h-4" />
        </button>
      </div>

      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-72 overflow-y-auto rounded-[10px] border border-[hsl(var(--border))] bg-[hsl(var(--card))] shadow-pop-xl animate-fade-in-down">
          <div className="flex items-center justify-between px-3 py-2 border-b border-[hsl(var(--border))] sticky top-0 bg-[hsl(var(--card))]">
            <span className="text-[11px] font-semibold text-[hsl(var(--slate-600))]">选择已打开的窗口</span>
            <button
              type="button"
              onClick={fetchWindows}
              className="flex items-center gap-1 text-[11px] text-[hsl(var(--brand-600))] hover:text-[hsl(var(--brand-700))]"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
              刷新
            </button>
          </div>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-6 text-[12px] text-[hsl(var(--muted-foreground))]">
              <Loader2 className="w-4 h-4 animate-spin" /> 正在枚举窗口…
            </div>
          ) : error ? (
            <div className="px-3 py-4 text-[12px] text-[hsl(var(--danger-600))]">{error}</div>
          ) : windows.length === 0 ? (
            <div className="px-3 py-4 text-[12px] text-[hsl(var(--muted-foreground))]">未检测到可见窗口</div>
          ) : (
            <div className="py-1">
              {windows.map((w) => (
                <button
                  key={w.hwnd}
                  type="button"
                  onClick={() => {
                    onChange(w.title)
                    setOpen(false)
                  }}
                  className="w-full text-left px-3 py-1.5 hover:bg-[hsl(var(--brand-50))] transition-colors"
                >
                  <div className="text-[12.5px] text-[hsl(var(--slate-800))] truncate">{w.title}</div>
                  <div className="text-[10.5px] text-[hsl(var(--muted-foreground))] truncate">{w.class}</div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
