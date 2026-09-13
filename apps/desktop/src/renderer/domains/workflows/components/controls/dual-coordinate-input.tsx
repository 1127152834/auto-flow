// Source: WebRPA@5ccb900e, components/ui/dual-coordinate-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { studioFetch } from '../../api/transport'
import { useState } from 'react'
import { Crosshair, Loader2 } from 'lucide-react'
import { NumberInput } from './number-input'
import { Button } from './button'
import { Label } from './label'
import { cn } from '../../lib/utils'
import { getBackendUrl } from '../../api'

interface DualCoordinateInputProps {
  xValue: number
  yValue: number
  onXChange: (value: number) => void
  onYChange: (value: number) => void
  onBothChange?: (x: number, y: number) => void  // 同时更新x和y
  label: string
  className?: string
}

export function DualCoordinateInput({
  xValue,
  yValue,
  onXChange,
  onYChange,
  onBothChange,
  label,
  className,
}: DualCoordinateInputProps) {
  const [isPicking, setIsPicking] = useState(false)
  const [statusText, setStatusText] = useState('')

  const handlePickPosition = async () => {
    if (isPicking) return
    
    setIsPicking(true)
    setStatusText('Ctrl+左键 确认 | Ctrl+右键/ESC 取消')
    
    try {
      const response = await studioFetch(`${getBackendUrl()}/api/system/pick-mouse-position`, {
        method: 'POST',
      })
      
      const result = await response.json()
      
      if (result.success && result.x !== null && result.y !== null) {
        // 使用onBothChange同时更新x和y，避免状态覆盖问题
        if (onBothChange) {
          console.log('[DualCoordinateInput] Calling onBothChange with:', result.x, result.y)
          onBothChange(result.x, result.y)
        } else {
          // 如果没有提供onBothChange，分别调用（可能会有状态覆盖问题）
          console.log('[DualCoordinateInput] Calling onXChange and onYChange separately')
          onXChange(result.x)
          onYChange(result.y)
        }
        setStatusText(`已获取: (${result.x}, ${result.y})`)
        setTimeout(() => setStatusText(''), 2000)
      } else if (result.cancelled) {
        setStatusText('已取消')
        setTimeout(() => setStatusText(''), 1500)
      } else {
        setStatusText('已取消')
        setTimeout(() => setStatusText(''), 1500)
      }
    } catch (error) {
      console.error('Failed to pick mouse position:', error)
      setStatusText('获取失败')
      setTimeout(() => setStatusText(''), 2000)
    } finally {
      setIsPicking(false)
    }
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between">
        <Label className="text-xs font-medium">{label}</Label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handlePickPosition}
          disabled={isPicking}
          className="h-6 px-2 text-xs gap-1"
          title="Ctrl+左键确认坐标"
        >
          {isPicking ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Crosshair className="h-3 w-3" />
          )}
          拾取
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground w-4">X:</span>
          <NumberInput
            value={xValue}
            onChange={(v) => onXChange(typeof v === 'number' ? v : parseInt(String(v)) || 0)}
            defaultValue={0}
            min={0}
          />
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs text-muted-foreground w-4">Y:</span>
          <NumberInput
            value={yValue}
            onChange={(v) => onYChange(typeof v === 'number' ? v : parseInt(String(v)) || 0)}
            defaultValue={0}
            min={0}
          />
        </div>
      </div>
      {statusText && (
        <p className={cn(
          'text-xs',
          statusText.includes('已获取') ? 'text-green-600' : 
          statusText.includes('失败') ? 'text-red-600' : 
          statusText.includes('取消') ? 'text-orange-600' :
          'text-blue-600'
        )}>
          {statusText}
        </p>
      )}
    </div>
  )
}
