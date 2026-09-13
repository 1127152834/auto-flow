import { useEffect, useState } from 'react'
import { getBackendBaseUrl } from '../../api/config'
import { studioFetch } from '../../api/transport'
import type { ImageAsset } from '../../types'

/** Image bytes use the same transport/authentication boundary as other Studio requests. */
export function ImageAssetPreview({ asset, variant = 'thumbnail', className }: {
  asset: Pick<ImageAsset, 'id' | 'path' | 'originalName'>
  variant?: 'thumbnail' | 'file'
  className?: string
}) {
  const source = asset.path?.startsWith('data:image/') ? asset.path : `${getBackendBaseUrl()}/api/image-assets/${encodeURIComponent(asset.id)}/${variant}`
  return <ResourceImage key={source} source={source} alt={asset.originalName} className={className} />
}

function ResourceImage({ source, alt, className }: { source: string; alt: string; className?: string }) {
  const inline = source.startsWith('data:image/')
  const [url, setUrl] = useState(inline ? source : '')
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (inline) return
    const controller = new AbortController()
    let objectUrl: string | undefined
    void (async () => {
      try {
        const response = await studioFetch(source, { signal: controller.signal })
        if (!response.ok) throw new Error(`图片读取失败（${response.status}）`)
        const blob = await response.blob()
        if (!blob.type.startsWith('image/')) throw new Error('服务返回的内容不是图片')
        if (controller.signal.aborted) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '图片读取失败')
      }
    })()
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [source, inline, attempt])

  if (error) return <button type="button" className="text-xs text-muted-foreground" title={error} onClick={event => {
    event.stopPropagation(); setError(''); setUrl(inline ? source : ''); setAttempt(value => value + 1)
  }} aria-label={`重新加载图片：${alt}`}>图片加载失败，重试</button>
  if (!url) return <span role="status" className="text-xs text-muted-foreground" aria-label={`加载图片：${alt}`}>加载中</span>
  return <img src={url} alt={alt} className={className} onError={() => setError('图片无法解码')} />
}
