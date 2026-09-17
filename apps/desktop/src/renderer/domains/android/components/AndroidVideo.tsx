import { useEffect, useRef, useState } from 'react'
import type { ConsoleSession, FleetApi, InputCommand } from '../fleet-api'
const codes: Record<string, number> = {
  Backspace: 67,
  Enter: 66,
  Escape: 4,
  Home: 3,
  Tab: 61,
  ArrowUp: 19,
  ArrowDown: 20,
  ArrowLeft: 21,
  ArrowRight: 22,
  Delete: 112,
  ' ': 62,
}
export function mapVideoPoint(
  clientX: number,
  clientY: number,
  bounds: { left: number; top: number; width: number; height: number },
  size: { width: number; height: number },
  clamp: boolean,
) {
  const { width, height } = size,
    scale = Math.min(bounds.width / width, bounds.height / height)
  if (!Number.isFinite(scale) || scale <= 0) return null
  const left = bounds.left + (bounds.width - width * scale) / 2,
    top = bounds.top + (bounds.height - height * scale) / 2
  if (!clamp && (clientX < left || clientY < top || clientX >= left + width * scale || clientY >= top + height * scale))
    return null
  return {
    x: Math.max(0, Math.min(width - 1, Math.floor((clientX - left) / scale))),
    y: Math.max(0, Math.min(height - 1, Math.floor((clientY - top) / scale))),
  }
}
export function waitForVideoDecoder(decoder: Pick<VideoDecoder, 'decodeQueueSize' | 'addEventListener' | 'removeEventListener'>, signal: AbortSignal): Promise<void> {
  if (decoder.decodeQueueSize < 8) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const finish = (error?: Error) => {
      clearTimeout(timeout)
      decoder.removeEventListener('dequeue', drained)
      signal.removeEventListener('abort', aborted)
      if (error) reject(error); else resolve()
    }
    const drained = () => { if (decoder.decodeQueueSize < 8) finish() }
    const aborted = () => finish(new Error('视频连接已结束'))
    const timeout = setTimeout(() => finish(new Error('设备画面解码超时，请重新连接')), 3000)
    decoder.addEventListener('dequeue', drained)
    signal.addEventListener('abort', aborted, {once:true})
    if (signal.aborted) aborted(); else drained()
  })
}

export function AndroidVideo({
  api,
  session,
  keyboard,
  send,
  onError,
  onReady,
}: {
  api: FleetApi
  session: ConsoleSession
  keyboard: boolean
  send(c: Partial<InputCommand>): void
  onError(message: string): void
  onReady?(ready: boolean): void
}) {
  const canvas = useRef<HTMLCanvasElement>(null),
    size = useRef({ width: session.width, height: session.height })
  const [ready, setReady] = useState(false),
    pointer = useRef<number | null>(null)
  const manual = session.access === 'manual' && session.endpoint === 'embedded'
  useEffect(() => {
    setReady(false)
    onReady?.(false)
    const controller = new AbortController()
    let decoder: VideoDecoder | null = null
    const run = async () => {
      if (!('VideoDecoder' in window)) throw new Error('当前浏览器不支持设备视频，请使用 AutoFlow 桌面应用')
      const response = await api.stream(session.id, controller.signal),
        reader = response.body?.getReader()
      if (!reader) throw new Error('设备未提供连续画面')
      let buffer = new Uint8Array(0),
        first = true,
        config = new Uint8Array(0),
        configured = false,
        needKey = true
      decoder = new VideoDecoder({
        output: (frame) => {
          if (controller.signal.aborted) { frame.close(); return }
          const target = canvas.current
          if (target) {
            target.width = frame.displayWidth
            target.height = frame.displayHeight
            size.current = { width: target.width, height: target.height }
            target.getContext('2d')?.drawImage(frame, 0, 0)
            setReady(true)
            onReady?.(true)
          }
          frame.close()
        },
        error: (e) => {
          controller.abort()
          setReady(false)
          onReady?.(false)
          onError(`画面解码失败：${e.message}`)
        },
      })
      try {
        for (;;) {
          const { done, value } = await reader.read()
          if (done) throw new Error('画面连接已断开，请重新打开设备')
          const next = new Uint8Array(buffer.length + value.length)
          next.set(buffer)
          next.set(value, buffer.length)
          buffer = next
          if (first) {
            if (buffer.length < 12) continue
            buffer = buffer.slice(12)
            first = false
          }
          while (buffer.length >= 12) {
            const view = new DataView(buffer.buffer, buffer.byteOffset),
              pts = view.getBigUint64(0),
              length = view.getUint32(8)
            if (length > 8 * 1024 * 1024) throw new Error('设备视频帧无效')
            if (buffer.length < length + 12) break
            const payload = buffer.slice(12, 12 + length)
            buffer = buffer.slice(12 + length)
            if (pts & (1n << 63n)) {
              config = payload
              const i = payload.findIndex(
                (v, index) =>
                  (v & 31) === 7 &&
                  index >= 3 &&
                  payload[index - 1] === 1 &&
                  payload[index - 2] === 0 &&
                  payload[index - 3] === 0,
              )
              if (i < 0) throw new Error('设备未提供 H264 配置')
              decoder.configure({
                codec: 'avc1.' + [...payload.slice(i + 1, i + 4)].map((v) => v.toString(16).padStart(2, '0')).join(''),
                optimizeForLatency: true,
              })
              configured = true
              needKey = true
              continue
            }
            const key = Boolean(pts & (1n << 62n))
            if (!configured || (needKey && !key)) continue
            await waitForVideoDecoder(decoder, controller.signal)
            const data = key ? new Uint8Array(config.length + payload.length) : payload
            if (key) {
              data.set(config)
              data.set(payload, config.length)
              needKey = false
            }
            decoder.decode(
              new EncodedVideoChunk({ type: key ? 'key' : 'delta', timestamp: Number(pts & ((1n << 62n) - 1n)), data }),
            )
          }
        }
      } finally {
        await reader.cancel().catch(() => undefined)
      }
    }
    void run().catch((e) => {
      if (!controller.signal.aborted) {
        setReady(false)
        onReady?.(false)
        onError(e instanceof Error ? e.message : '画面连接失败')
      }
    })
    return () => {
      controller.abort()
      if (decoder && decoder.state !== 'closed') decoder.close()
    }
  }, [api, session.id, session.generation, onError, onReady])
  const touch = (e: React.PointerEvent<HTMLCanvasElement>, action: number) => {
    if (!manual || !ready) return
    const bounds = e.currentTarget.getBoundingClientRect(),
      { width, height } = size.current
    const point = mapVideoPoint(e.clientX, e.clientY, bounds, size.current, action !== 0)
    if (!point) return false
    const { x, y } = point
    send({ kind: 'touch', action, x, y, width, height })
    return true
  }
  return (
    <>
      <canvas
        ref={canvas}
        tabIndex={manual ? 0 : -1}
        aria-label={manual ? '安卓触控画面' : '安卓只读画面'}
        onContextMenu={(e) => e.preventDefault()}
        onPointerDown={(e) => {
          if (!manual || !ready || pointer.current !== null) return
          e.currentTarget.focus()
          if (touch(e, 0)) {
            pointer.current = e.pointerId
            e.currentTarget.setPointerCapture(e.pointerId)
          }
        }}
        onPointerMove={(e) => {
          if (pointer.current === e.pointerId && e.currentTarget.hasPointerCapture(e.pointerId)) touch(e, 2)
        }}
        onPointerUp={(e) => {
          if (pointer.current !== e.pointerId) return
          touch(e, 1)
          pointer.current = null
          e.currentTarget.releasePointerCapture(e.pointerId)
        }}
        onPointerCancel={() => {
          pointer.current = null
          if (manual) send({ kind: 'release' })
        }}
        onBlur={() => {
          if (manual) send({ kind: 'release' })
        }}
        onKeyDown={(e) => {
          if (!manual || !keyboard) return
          e.preventDefault()
          const code = codes[e.key]
          if (code) send({ kind: 'key', keycode: code, action: 0 })
          else if (e.key.length === 1 && !e.metaKey && !e.ctrlKey) send({ kind: 'text', text: e.key })
        }}
        onKeyUp={(e) => {
          if (manual && keyboard && codes[e.key]) {
            e.preventDefault()
            send({ kind: 'key', keycode: codes[e.key], action: 1 })
          }
        }}
      />
      {!ready && <span className="ad-video-wait">正在连接设备画面…</span>}
    </>
  )
}
