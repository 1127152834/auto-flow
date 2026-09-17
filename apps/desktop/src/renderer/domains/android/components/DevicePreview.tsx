import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { DeviceMobile } from '@phosphor-icons/react'
import { useApi } from '../../../app/ApiProvider'
import type { AndroidApi, AndroidDevice } from '../api'

export function DevicePreview({ device, api, large = false, enabled = true }: { device: AndroidDevice; api: AndroidApi; large?: boolean; enabled?: boolean }) {
  const { instanceId } = useApi()
  const available = enabled && device.androidStatus === 'ready' && !['managing', 'recovery_required'].includes(device.control)
  const query = useQuery({ queryKey: ['android-preview', instanceId, device.deviceId], queryFn: ({ signal }) => api.preview(device.deviceId, signal), enabled: available, refetchInterval: 10000, retry: false })
  const [url, setUrl] = useState('')
  useEffect(() => {
    if (!query.data) return
    const objectUrl = URL.createObjectURL(query.data)
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [query.data])
  const visible = available && !query.isError && url
  return <div className={`flex shrink-0 flex-col items-center justify-center gap-2 ${large ? 'w-full py-6' : 'w-[76px]'}`}>
    {visible ? <img src={url} alt={`${device.name}的只读画面`} className={`rounded-control border border-line object-contain ${large ? 'max-h-[480px] max-w-full' : 'max-h-40 w-[72px]'}`} /> : <div className={`flex flex-col items-center justify-center gap-3 text-muted ${large ? 'min-h-72' : 'h-32'}`}><DeviceMobile size={large ? 52 : 32} weight="light" /><span className="text-center text-[11px]">{query.isError ? '预览不可用' : available ? '读取画面…' : '暂无在线画面'}</span></div>}
    {large && <p className="text-xs text-muted">{visible ? `只读截图 · ${new Date(query.dataUpdatedAt).toLocaleTimeString()} · 每10秒更新` : '设备就绪后显示只读截图'}<br />手动操作请打开独立 Mac 窗口。</p>}
  </div>
}
