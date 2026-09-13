// Source: WebRPA@5ccb900e, components/ui/phone-coordinate-input.tsx; see SOURCE.md for license and adaptation boundaries.
import { useEffect, useRef, useState } from 'react'
import { Crosshair, Loader2, Play, X as XIcon } from 'lucide-react'
import { VariableInput } from './variable-input'
import { Button } from './button'
import { cn } from '../../lib/utils'
import { phoneApi } from '../../api'

interface PhoneCoordinateInputProps {
  xValue: string
  yValue: string
  onXChange: (value: string) => void
  onYChange: (value: string) => void
  deviceId?: string  // 指定的设备ID
  xPlaceholder?: string
  yPlaceholder?: string
  className?: string
}

export function PhoneCoordinateInput({
  xValue,
  yValue,
  onXChange,
  onYChange,
  deviceId: propDeviceId,
  xPlaceholder = '手机屏幕X坐标',
  yPlaceholder = '手机屏幕Y坐标',
  className,
}: PhoneCoordinateInputProps) {
  const [isTesting, setIsTesting] = useState(false)
  const [isPicking, setIsPicking] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [statusKind, setStatusKind] = useState<'success' | 'error' | 'info' | ''>('')
  const [defaultDeviceId, setDefaultDeviceId] = useState<string | null>(null)
  const pollTimerRef = useRef<number | null>(null)

  const setStatus = (text: string, kind: 'success' | 'error' | 'info' | '' = 'info', clearAfter = 0) => {
    setStatusText(text)
    setStatusKind(kind)
    if (clearAfter > 0) {
      setTimeout(() => {
        setStatusText('')
        setStatusKind('')
      }, clearAfter)
    }
  }

  const checkDevice = async () => {
    try {
      const result = await phoneApi.getDevices()
      if (result.data?.devices && result.data.devices.length > 0) {
        setDefaultDeviceId(result.data.devices[0].id)
        return result.data.devices[0].id
      }
      return null
    } catch {
      return null
    }
  }

  useEffect(() => {
    if (!propDeviceId) {
      checkDevice()
    }
  }, [propDeviceId])

  // 组件卸载时停掉拾取（避免镜像窗口残留）
  useEffect(() => {
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
      // 卸载时如果 picker 还在运行，关掉
      if (isPicking) {
        phoneApi.stopCoordinatePicker().catch(() => {})
      }
    }

  }, [])

  const handleTest = async () => {
    const x = parseInt(xValue)
    const y = parseInt(yValue)

    if (isNaN(x) || isNaN(y)) {
      setStatus('请先输入有效的坐标', 'error', 2000)
      return
    }

    const targetDeviceId = propDeviceId || defaultDeviceId
    if (!targetDeviceId) {
      setStatus('未检测到设备', 'error', 2000)
      return
    }

    setIsTesting(true)
    setStatus(`正在测试坐标 (${x}, ${y})...`, 'info')

    try {
      const result = await phoneApi.testCoordinate(x, y, targetDeviceId)
      if (result.data?.success) {
        setStatus(`已在设备 ${targetDeviceId} 上点击坐标 (${x}, ${y})`, 'success', 3000)
      } else {
        setStatus(`测试失败: ${result.data?.error || result.error || '未知错误'}`, 'error', 3000)
      }
    } catch (error) {
      console.error('Failed to test:', error)
      setStatus('测试失败', 'error', 2000)
    } finally {
      setIsTesting(false)
    }
  }

  // 启动坐标拾取：弹出/复用手机镜像窗口，按 Ctrl+点击 拾取
  const handlePick = async () => {
    const targetDeviceId = propDeviceId || defaultDeviceId
    if (!targetDeviceId) {
      setStatus('未检测到设备', 'error', 2000)
      return
    }
    setIsPicking(true)
    setStatus('正在打开手机镜像…', 'info')
    try {
      const startRes = await phoneApi.startCoordinatePicker(targetDeviceId, true)
      if (!startRes.data?.success) {
        setIsPicking(false)
        setStatus(`启动拾取失败：${startRes.data?.error || startRes.error || '未知错误'}`, 'error', 3000)
        return
      }
      setStatus('请在手机镜像中按住 Ctrl 并点击目标位置（普通点击会正常操作手机）', 'info')

      // 轮询直到拾取成功（或用户取消）
      pollTimerRef.current = window.setInterval(async () => {
        try {
          const res = await phoneApi.getPickedCoordinate()
          if (res.data?.picked && typeof res.data.x === 'number' && typeof res.data.y === 'number') {
            // 拿到坐标后立即停掉
            if (pollTimerRef.current !== null) {
              window.clearInterval(pollTimerRef.current)
              pollTimerRef.current = null
            }
            const x = res.data.x
            const y = res.data.y
            onXChange(String(x))
            onYChange(String(y))
            await phoneApi.stopCoordinatePicker().catch(() => {})
            setIsPicking(false)
            setStatus(`已拾取坐标 (${x}, ${y})`, 'success', 3000)
          }
        } catch {
          // 忽略轮询错误，继续尝试
        }
      }, 350)
    } catch (e) {
      setIsPicking(false)
      setStatus(`启动拾取异常：${(e as Error)?.message || e}`, 'error', 3000)
    }
  }

  // 取消拾取
  const handleCancelPick = async () => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
    try { await phoneApi.stopCoordinatePicker() } catch {}
    setIsPicking(false)
    setStatus('已取消拾取', 'info', 1500)
  }

  const targetDevice = propDeviceId || defaultDeviceId

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
        <div className="flex flex-col gap-1">
          {/* 拾取坐标按钮 */}
          {!isPicking ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePick}
              disabled={!targetDevice || isTesting}
              className="h-8 px-3 flex items-center justify-center gap-1"
              title="点击后弹出手机镜像；按住 Ctrl 并点击屏幕即可拾取坐标"
            >
              <Crosshair className="h-3 w-3" />
              <span className="text-xs whitespace-nowrap">拾取</span>
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCancelPick}
              className="h-8 px-3 flex items-center justify-center gap-1 text-orange-600 border-orange-300"
              title="取消拾取并关闭镜像窗口"
            >
              <XIcon className="h-3 w-3" />
              <span className="text-xs whitespace-nowrap">取消</span>
            </Button>
          )}
          {/* 测试按钮 */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={isTesting || isPicking || !xValue || !yValue || !targetDevice}
            className="h-8 px-3 flex items-center justify-center gap-1"
            title="在手机上测试当前坐标"
          >
            {isTesting ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                <span className="text-xs whitespace-nowrap">测试中</span>
              </>
            ) : (
              <>
                <Play className="h-3 w-3" />
                <span className="text-xs whitespace-nowrap">测试</span>
              </>
            )}
          </Button>
        </div>
      </div>
      {statusText ? (
        <p className={cn(
          'text-xs',
          statusKind === 'success' ? 'text-green-600' :
          statusKind === 'error' ? 'text-red-600' :
          'text-blue-600'
        )}>
          {statusText}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          点击「拾取」可弹出手机镜像，按住 <kbd className="px-1 py-0.5 rounded bg-muted text-[10px]">Ctrl</kbd> 并点击屏幕拾取坐标；不按 Ctrl 时可正常操作手机。点击「测试」可在手机上验证当前坐标。
        </p>
      )}
    </div>
  )
}
