// Source: WebRPA@5ccb900e, components/ui/password-prompt.tsx; see SOURCE.md for license and adaptation boundaries.
import { useCallback, useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Lock, Eye, EyeOff } from 'lucide-react'
import { Button } from './button'

interface PromptOptions {
  title?: string
  message?: string
  confirmText?: string
  placeholder?: string
  /** 最少位数（不足时确认禁用） */
  minLength?: number
}

/**
 * WebRPA 主题化密码输入弹窗（promise 式）。
 * 用法：
 *   const { promptPassword, passwordDialog } = usePasswordPrompt()
 *   const pwd = await promptPassword({ title: '设置加密密码' })  // 取消返回 null
 *   ...JSX 中渲染 {passwordDialog}
 *
 * 替代浏览器原生 prompt，符合「编辑器内禁止原生弹窗」要求。
 */
export function usePasswordPrompt() {
  const [state, setState] = useState<{ open: boolean; opts: PromptOptions }>({ open: false, opts: {} })
  const [value, setValue] = useState('')
  const [show, setShow] = useState(false)
  const resolveRef = useRef<((v: string | null) => void) | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const promptPassword = useCallback((opts: PromptOptions = {}) => {
    // A replaced prompt must resolve its original caller instead of leaving it suspended.
    resolveRef.current?.(null)
    setValue('')
    setShow(false)
    setState({ open: true, opts })
    return new Promise<string | null>((resolve) => { resolveRef.current = resolve })
  }, [])

  useEffect(() => () => {
    resolveRef.current?.(null)
    resolveRef.current = null
  }, [])

  useEffect(() => {
    if (state.open) {
      const t = setTimeout(() => inputRef.current?.focus(), 60)
      return () => clearTimeout(t)
    }
  }, [state.open])

  const close = (result: string | null) => {
    resolveRef.current?.(result)
    resolveRef.current = null
    setState({ open: false, opts: {} })
  }

  const minLen = state.opts.minLength ?? 0
  const tooShort = value.length < minLen
  const canConfirm = value.length > 0 && !tooShort

  const passwordDialog = state.open
    ? createPortal(
        <div
          className="fixed inset-0 z-[2147483646] bg-black/45 backdrop-blur-sm flex items-center justify-center px-4 animate-fade-in"
          onClick={() => close(null)}
        >
          <div
            className="w-full max-w-[420px] rounded-[14px] bg-[hsl(var(--card))] shadow-pop-2xl border border-[hsl(var(--border))] overflow-hidden animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 px-5 pt-5 pb-3">
              <span className="flex items-center justify-center w-10 h-10 rounded-[10px] bg-[hsl(var(--brand-50))] text-[hsl(var(--brand-600))] border border-[hsl(var(--brand-500)/0.25)]">
                <Lock className="w-5 h-5" strokeWidth={2.2} />
              </span>
              <div className="min-w-0">
                <div className="text-[15px] font-bold text-[hsl(var(--slate-900))]">{state.opts.title || '请输入密码'}</div>
                {state.opts.message && <div className="text-[12px] text-[hsl(var(--muted-foreground))] mt-0.5">{state.opts.message}</div>}
              </div>
            </div>
            <div className="px-5 pb-1">
              <div className="relative">
                <input
                  ref={inputRef}
                  type={show ? 'text' : 'password'}
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && canConfirm) close(value)
                    if (e.key === 'Escape') close(null)
                  }}
                  placeholder={state.opts.placeholder || '请输入密码'}
                  className="w-full h-10 pl-3 pr-10 text-[14px] rounded-[8px] border-[1.5px] border-[hsl(var(--border))] bg-[hsl(var(--slate-50))] focus:outline-none focus:bg-[hsl(var(--card))] focus:border-[hsl(var(--brand-500))] focus:ring-2 focus:ring-[hsl(var(--brand-500)/0.18)] transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--brand-600))]"
                  title={show ? '隐藏' : '显示'}
                >
                  {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {tooShort && value.length > 0 && (
                <div className="text-[11.5px] text-[hsl(var(--danger-600))] mt-1.5">密码至少需要 {minLen} 位</div>
              )}
            </div>
            <div className="flex items-center justify-end gap-2 px-5 py-3.5 mt-2 bg-[hsl(var(--slate-50))] border-t border-[hsl(var(--border))]">
              <Button variant="secondary" size="sm" onClick={() => close(null)}>取消</Button>
              <Button variant="default" size="sm" disabled={!canConfirm} onClick={() => close(value)}>{state.opts.confirmText || '确定'}</Button>
            </div>
          </div>
        </div>,
        document.body,
      )
    : null

  return { promptPassword, passwordDialog }
}
