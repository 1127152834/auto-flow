import { useEffect, useState } from 'react'

/** Shows the configured retry wait, never an invented provider cooldown. */
export function ProxyRetryCountdown({ retryAt, active }: { retryAt: unknown; active: boolean }) {
  const [now, setNow] = useState(Date.now)
  const valid = typeof retryAt === 'number' && Number.isFinite(retryAt)
  useEffect(() => {
    if (!active || !valid) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active, valid, retryAt])
  if (!active || !valid || retryAt <= now) return null
  return <span className="ml-2 text-xs tabular-nums" aria-label="代理重试倒计时">距下轮约 {Math.ceil((retryAt - now) / 1000)} 秒</span>
}
