import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { DeviceMobile } from '@phosphor-icons/react'
import { useApi } from '../../../app/ApiProvider'
import type { AndroidApi, AndroidDevice } from '../api'

let activePreviewRequests = 0
const pendingPreviewRequests: Array<{ resolve: (release: () => void) => void }> = []

function releasePreviewSlot() {
  activePreviewRequests -= 1
  while (activePreviewRequests < 2 && pendingPreviewRequests.length) {
    const pending = pendingPreviewRequests.shift()!
    activePreviewRequests += 1
    pending.resolve(releasePreviewSlot)
  }
}

function acquirePreviewSlot(signal: AbortSignal): Promise<() => void> {
  if (signal.aborted) return Promise.reject(signal.reason)
  if (activePreviewRequests < 2) {
    activePreviewRequests += 1
    return Promise.resolve(releasePreviewSlot)
  }
  return new Promise((resolve, reject) => {
    const pending = { resolve: (release: () => void) => {
      signal.removeEventListener('abort', cancel)
      resolve(release)
    } }
    const cancel = () => {
      const index = pendingPreviewRequests.indexOf(pending)
      if (index !== -1) pendingPreviewRequests.splice(index, 1)
      reject(signal.reason)
    }
    signal.addEventListener('abort', cancel, { once: true })
    pendingPreviewRequests.push(pending)
  })
}

function PreviewPlaceholder({ large, message }: { large: boolean; message: string }) {
  return <div className={`flex flex-col items-center justify-center gap-3 text-muted ${large ? 'min-h-72' : 'h-32'}`}><DeviceMobile size={large ? 52 : 32} weight="light" /><span className="text-center text-[11px]">{message}</span></div>
}

function VisiblePreview({ device, api, large, revision }: { device: AndroidDevice; api: AndroidApi; large: boolean; revision?: number }) {
  const { instanceId } = useApi()
  const query = useQuery({
    queryKey: ['android-preview', instanceId, device.deviceId, device.generation, revision ?? 0],
    queryFn: async ({ signal }) => {
      const release = await acquirePreviewSlot(signal)
      try {
        signal.throwIfAborted()
        return await api.preview(device.deviceId, signal)
      } finally { release() }
    },
    staleTime: 5000, refetchInterval: 5000, retry: false,
  })
  const [image, setImage] = useState<{ blob: Blob; url: string } | null>(null)
  useEffect(() => {
    if (!query.data) { setImage(null); return }
    const url = URL.createObjectURL(query.data)
    setImage({ blob: query.data, url })
    return () => URL.revokeObjectURL(url)
  }, [query.data])
  const visible = !query.isError && image?.blob === query.data && image
  return <>
    {visible ? <img src={visible.url} alt={`${device.name}的只读画面`} className={`rounded-control border border-line object-contain ${large ? 'max-h-[480px] max-w-full' : 'max-h-40 w-[72px]'}`} /> : <PreviewPlaceholder large={large} message={query.isError ? '预览不可用' : '读取画面…'} />}
    {large && <p className="text-xs text-muted">{visible ? `只读截图 · ${new Date(query.dataUpdatedAt).toLocaleTimeString()} · 每5秒更新` : '设备就绪后显示只读截图'}<br />手动操作请打开独立 Mac 窗口。</p>}
  </>
}

export function DevicePreview({ device, api, large = false, enabled = true, revision }: { device: AndroidDevice; api: AndroidApi; large?: boolean; enabled?: boolean; revision?: number }) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [inViewport, setInViewport] = useState(() => typeof IntersectionObserver === 'undefined')
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
  // Removing the query observer aborts its request when no visible consumer remains.
  return <div ref={hostRef} className={`flex shrink-0 flex-col items-center justify-center gap-2 ${large ? 'w-full py-6' : 'w-[76px]'}`}>
    {available ? <VisiblePreview device={device} api={api} large={large} revision={revision} /> : <PreviewPlaceholder large={large} message="暂无在线画面" />}
  </div>
}
