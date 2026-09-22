import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { DeviceMobile } from '@phosphor-icons/react'
import { useApi } from '../../../app/ApiProvider'
import type { AndroidApi, AndroidDevice } from '../api'

let activePreviewRequests = 0
const pendingPreviewRequests: Array<{ resolve: (release: () => void) => void; signal: AbortSignal }> = []

function releasePreviewSlot() {
  activePreviewRequests -= 1
  while (activePreviewRequests < 2 && pendingPreviewRequests.length) {
    const pending = pendingPreviewRequests.shift()!
    if (pending.signal.aborted) continue
    activePreviewRequests += 1
    pending.resolve(() => releasePreviewSlot())
  }
}

function acquirePreviewSlot(signal: AbortSignal): Promise<() => void> {
  if (signal.aborted) return Promise.reject(signal.reason)
  if (activePreviewRequests < 2) {
    activePreviewRequests += 1
    return Promise.resolve(() => releasePreviewSlot())
  }
  return new Promise((resolve) => pendingPreviewRequests.push({ resolve, signal }))
}

export function DevicePreview({ device, api, large = false, enabled = true, revision }: { device: AndroidDevice; api: AndroidApi; large?: boolean; enabled?: boolean; revision?: number }) {
  const { instanceId } = useApi()
  const hostRef = useRef<HTMLDivElement>(null)
  const [inViewport, setInViewport] = useState(true)
  const [hidden, setHidden] = useState(() => typeof document !== 'undefined' && document.visibilityState === 'hidden')
  useEffect(() => {
    const onVisibility = () => setHidden(document.visibilityState === 'hidden')
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [])
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined' || !hostRef.current) return
    const observer = new IntersectionObserver((entries) => setInViewport(entries.some((entry) => entry.isIntersecting)))
    observer.observe(hostRef.current)
    return () => observer.disconnect()
  }, [])
  const available = enabled && !hidden && inViewport && device.androidStatus === 'ready' && !['managing', 'recovery_required'].includes(device.control)
  const query = useQuery({ queryKey: ['android-preview', instanceId, device.deviceId, device.generation, revision ?? 0], queryFn: async ({ signal }) => { const release = await acquirePreviewSlot(signal); try { return await api.preview(device.deviceId, signal) } finally { release() } }, enabled: available, staleTime: 5000, refetchInterval: 5000, retry: false })
  const [url, setUrl] = useState('')
  const objectUrlRef = useRef<string | undefined>(undefined)
  useEffect(() => {
    const previous = objectUrlRef.current
    if (previous) URL.revokeObjectURL(previous)
    objectUrlRef.current = undefined
    setUrl('')
    if (!available || !query.data) return
    const objectUrl = URL.createObjectURL(query.data)
    objectUrlRef.current = objectUrl
    setUrl(objectUrl)
    return () => {
      if (objectUrlRef.current !== objectUrl) return
      URL.revokeObjectURL(objectUrl)
      objectUrlRef.current = undefined
      setUrl('')
    }
  }, [available, query.data])
  const visible = available && !query.isError && url
  return <div ref={hostRef} className={`flex shrink-0 flex-col items-center justify-center gap-2 ${large ? 'w-full py-6' : 'w-[76px]'}`}>
    {visible ? <img src={url} alt={`${device.name}的只读画面`} className={`rounded-control border border-line object-contain ${large ? 'max-h-[480px] max-w-full' : 'max-h-40 w-[72px]'}`} /> : <div className={`flex flex-col items-center justify-center gap-3 text-muted ${large ? 'min-h-72' : 'h-32'}`}><DeviceMobile size={large ? 52 : 32} weight="light" /><span className="text-center text-[11px]">{query.isError ? '预览不可用' : available ? '读取画面…' : '暂无在线画面'}</span></div>}
    {large && <p className="text-xs text-muted">{visible ? `只读截图 · ${new Date(query.dataUpdatedAt).toLocaleTimeString()} · 每5秒更新` : '设备就绪后显示只读截图'}<br />手动操作请打开独立 Mac 窗口。</p>}
  </div>
}
