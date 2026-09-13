// Source: WebRPA@5ccb900e, components/ui/coordinate-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { studioFetch } from '../../api/transport'
import { useState } from 'react'
import { Crosshair, Loader2 } from 'lucide-react'
import { VariableInput } from './variable-input'
import { Button } from './button'
import { cn } from '../../lib/utils'
import { getBackendUrl } from '../../api'

interface CoordinateInputProps {
  xValue: string
  yValue: string
  onXChange: (value: string) => void
  onYChange: (value: string) => void
  xPlaceholder?: string
  yPlaceholder?: string
  className?: string
}

export function CoordinateInput({
  xValue,
  yValue,
  onXChange,
  onYChange,
  xPlaceholder = '屏幕X坐标',
  yPlaceholder = '屏幕Y坐标',
  className,
}: CoordinateInputProps) {
  const [isPicking, setIsPicking] = useState(false)
  const [statusText, setStatusText] = useState('')

  const handlePickPosition = async () => {
    if (isPicking) return
    
    setIsPicking(true)
    setStatusText('Ctrl+左键 确认坐标 | Ctrl+右键 或 ESC 取消')
    
    try {
      const response = await studioFetch(`${getBackendUrl()}/api/system/pick-mouse-position`, {
        method: 'POST',
      })
      
      const result = await response.json()
      
      if (result.success && result.x !== null && result.y !== null) {
        onXChange(String(result.x))
        onYChange(String(result.y))
        setStatusText(`已获取坐标: (${result.x}, ${result.y})`)
        setTimeout(() => setStatusText(''), 3000)
      } else if (result.cancelled) {
        setStatusText('已取消')
        setTimeout(() => setStatusText(''), 2000)
      } else if (result.error) {
        setStatusText(`获取失败: ${result.error}`)
        setTimeout(() => setStatusText(''), 3000)
      } else {
        setStatusText('已取消')
        setTimeout(() => setStatusText(''), 2000)
      }
    } catch (error) {
      console.error('Failed to pick mouse position:', error)
      setStatusText('获取坐标失败，请确保后端服务已启动')
      setTimeout(() => setStatusText(''), 3000)
    } finally {
      setIsPicking(false)
    }
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center gap-2">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-6">X:</span>
            <VariableInput
              value={xValue}
              onChange={onXChange}
              placeholder={xPlaceholder}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-6">Y:</span>
            <VariableInput
              value={yValue}
              onChange={onYChange}
              placeholder={yPlaceholder}
            />
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handlePickPosition}
          disabled={isPicking}
          className="h-[68px] px-3 flex flex-col items-center justify-center gap-1"
          title="Ctrl+左键确认坐标，Ctrl+右键取消"
        >
          {isPicking ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-xs">拾取中</span>
            </>
          ) : (
            <>
              <Crosshair className="h-4 w-4" />
              <span className="text-xs">拾取</span>
            </>
          )}
        </Button>
      </div>
      {statusText ? (
        <p className={cn(
          'text-xs',
          statusText.includes('已获取') ? 'text-green-600' : 
          statusText.includes('失败') ? 'text-red-600' : 
          statusText.includes('取消') ? 'text-orange-600' :
          'text-blue-600'
        )}>
          {statusText}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          点击「拾取」后，按 Ctrl+左键 确认坐标，Ctrl+右键 或 ESC 取消
        </p>
      )}
    </div>
  )
}
