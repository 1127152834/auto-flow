// Source: WebRPA@5ccb900e, components/workflow/RemoteCursor.tsx; see SOURCE.md for license and adaptation boundaries.
/**
 * 远程光标组件 - 显示远程协助者的鼠标位置（画布坐标系）
 */

import { useEffect, useState, useRef } from 'react'
import { remoteService } from '../api/remote'

interface CursorPosition {
  flowX: number  // 画布坐标
  flowY: number
  visible: boolean
}

interface RemoteCursorProps {
  flowToScreenPosition: (position: { x: number; y: number }) => { x: number; y: number }
}

export function RemoteCursor({ flowToScreenPosition }: RemoteCursorProps) {
  const [position, setPosition] = useState<CursorPosition>({ flowX: 0, flowY: 0, visible: false })
  const [screenPos, setScreenPos] = useState({ x: 0, y: 0 })
  const [isClicking, setIsClicking] = useState(false)
  const hideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 监听远程鼠标消息
  useEffect(() => {
    const unsubscribe = remoteService.onMessage((message) => {
      if (message.type === 'mouse_move') {
        const { x, y } = message as { type: string; x: number; y: number }
        
        if (hideTimeoutRef.current) {
          clearTimeout(hideTimeoutRef.current)
        }

        setPosition({ flowX: x, flowY: y, visible: true })

        // 3秒无移动后隐藏光标
        hideTimeoutRef.current = setTimeout(() => {
          setPosition(prev => ({ ...prev, visible: false }))
        }, 3000)
      } else if (message.type === 'mouse_click') {
        setIsClicking(true)
        setTimeout(() => setIsClicking(false), 200)
      }
    })

    return () => {
      unsubscribe()
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current)
      }
    }
  }, [])

  // 将画布坐标转换为屏幕坐标（每帧更新，跟随视口变化）
  useEffect(() => {
    if (!position.visible) return

    let rafId: number
    const updateScreenPos = () => {
      const screen = flowToScreenPosition({ x: position.flowX, y: position.flowY })
      setScreenPos(screen)
      rafId = requestAnimationFrame(updateScreenPos)
    }
    
    rafId = requestAnimationFrame(updateScreenPos)
    return () => cancelAnimationFrame(rafId)
  }, [position.flowX, position.flowY, position.visible, flowToScreenPosition])

  if (!position.visible) {
    return null
  }

  return (
    <div
      className="pointer-events-none fixed z-[9999]"
      style={{
        left: screenPos.x,
        top: screenPos.y,
        transform: 'translate(-2px, -2px)',
      }}
    >
      {/* 光标图标 */}
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        className={`drop-shadow-lg transition-transform ${isClicking ? 'scale-90' : 'scale-100'}`}
      >
        <path
          d="M5.5 3.21V20.8c0 .45.54.67.85.35l4.86-4.86a.5.5 0 0 1 .35-.15h6.87c.48 0 .72-.58.38-.92L6.35 2.85a.5.5 0 0 0-.85.36Z"
          fill="#8B5CF6"
          stroke="#fff"
          strokeWidth="1.5"
        />
      </svg>
      
      {/* 标签 */}
      <div className="absolute left-5 top-4 bg-purple-500 text-white text-xs px-2 py-0.5 rounded-control whitespace-nowrap shadow-md">
        对方
      </div>

      {/* 点击效果 */}
      {isClicking && (
        <div className="absolute left-0 top-0 w-8 h-8 -translate-x-1/2 -translate-y-1/2 rounded-full bg-purple-400/30 animate-ping" />
      )}
    </div>
  )
}
