import { describe, expect, it } from 'vitest'
import { mapVideoPoint, waitForVideoDecoder } from '../components/AndroidVideo'
describe('video coordinates', () => {
  const bounds = { left: 100, top: 50, width: 300, height: 600 }
  it('maps the contained portrait picture, excluding unused margins', () => {
    expect(mapVideoPoint(250, 350, bounds, { width: 720, height: 1280 }, false)).toEqual({ x: 360, y: 640 })
    expect(mapVideoPoint(250, 51, bounds, { width: 720, height: 1280 }, false)).toBeNull()
  })
  it('uses landscape dimensions after rotation and clamps a captured pointer release', () => {
    expect(mapVideoPoint(250, 350, bounds, { width: 1280, height: 720 }, false)).toEqual({ x: 640, y: 360 })
    expect(mapVideoPoint(250, 100, bounds, { width: 1280, height: 720 }, false)).toBeNull()
    expect(mapVideoPoint(900, 900, bounds, { width: 1280, height: 720 }, true)).toEqual({ x: 1279, y: 719 })
  })
})

it('waits for queued video to drain instead of rejecting a cached GOP burst', async () => {
  const decoder = Object.assign(new EventTarget(), {decodeQueueSize: 30})
  let completed = false
  const result = waitForVideoDecoder(decoder as unknown as VideoDecoder, new AbortController().signal).then(() => {completed = true})
  await Promise.resolve()
  expect(completed).toBe(false)
  decoder.decodeQueueSize = 7
  decoder.dispatchEvent(new Event('dequeue'))
  await result
  expect(completed).toBe(true)
})
it('aborts a pending video queue wait on session close', async () => {
  const decoder = Object.assign(new EventTarget(), {decodeQueueSize: 30}), controller = new AbortController()
  const result = waitForVideoDecoder(decoder as unknown as VideoDecoder, controller.signal)
  controller.abort()
  await expect(result).rejects.toThrow('视频连接已结束')
})
