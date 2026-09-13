import { useEffect, useRef, useState } from 'react'
import { systemApi } from '../api'
import { Button } from './controls/button'

export function StudioConnectionNotice() {
  const [unavailable, setUnavailable] = useState(false)
  const [checking, setChecking] = useState(false)
  const failures = useRef(0)
  const pending = useRef(false)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    const onFailure = () => { failures.current++; setUnavailable(true) }
    const onRecovery = () => { failures.current++; setUnavailable(false) }
    window.addEventListener('studio:connection-error', onFailure)
    window.addEventListener('studio:connection-restored', onRecovery)
    return () => {
      mounted.current = false
      window.removeEventListener('studio:connection-error', onFailure)
      window.removeEventListener('studio:connection-restored', onRecovery)
    }
  }, [])
  const retry = async () => {
    if (pending.current) return
    pending.current = true
    setChecking(true)
    const revision = failures.current
    try {
      const result = await systemApi.getConfig()
      if (mounted.current && result.success && revision === failures.current) setUnavailable(false)
    } catch {
      // 检查失败时保留离线提示，允许用户再次重试。
    } finally {
      pending.current = false
      if (mounted.current) setChecking(false)
    }
  }
  if (!unavailable) return null
  return <div role="alert" className="flex items-center gap-3 border-b border-amber-300 bg-amber-50 px-3 py-2 text-xs">
    <span>服务连接不可用，当前草稿仍保留。请检查连接后重试。</span>
    <Button size="sm" variant="outline" disabled={checking} onClick={() => void retry()}>
      {checking ? '正在检查连接' : '重试连接'}
    </Button>
  </div>
}
