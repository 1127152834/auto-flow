// Source: WebRPA@5ccb900e, components/ui/dialog-portal.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 通用对话框 Portal 包装器
 *
 * 用途：把任何半透明遮罩弹窗渲染到 document.body，
 * 突破上层 transform / filter / will-change 创建的 stacking context，
 * 确保遮罩永远盖住整个屏幕、对话框永远在最高层级。
 *
 * 用法：
 *   <DialogPortal>
 *     <div className="fixed inset-0 ...">...</div>
 *   </DialogPortal>
 */
import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  children: ReactNode
}

export function DialogPortal({ children }: Props) {
  // SSR 兼容（Vite 通常不需要，但保险）
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])
  if (!mounted) return null
  return createPortal(children, document.body)
}
