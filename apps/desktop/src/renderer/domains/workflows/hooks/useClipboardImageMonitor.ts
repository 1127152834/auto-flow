// Source: WebRPA@5ccb900e, hooks/useClipboardImageMonitor.ts; see SOURCE.md for license and adaptation boundaries.
import { useEffect } from 'react'
import { socketService } from '../events'
import { useGlobalConfigStore } from './stores/globalConfigStore'

/**
 * 监听剪贴板中的新图片
 * 当检测到新图片时，弹出对话框询问用户是否保存
 */
export function useClipboardImageMonitor(onNewImage: (width: number, height: number) => void) {
  const autoDetect = useGlobalConfigStore((state) => state.config.system.autoDetectClipboardScreenshot)
  
  useEffect(() => {
    // 如果未开启自动识别，则不监听
    if (!autoDetect) {
      return
    }
    
    const handleClipboardNewImage = (data: any) => {
      console.log('[ClipboardMonitor] 检测到新图片:', data)
      onNewImage(data.width, data.height)
    }

    // 监听后端的剪贴板新图片事件
    socketService.on('clipboard:new_image', handleClipboardNewImage)

    return () => {
      socketService.off('clipboard:new_image', handleClipboardNewImage)
    }
  }, [onNewImage, autoDetect])
}
