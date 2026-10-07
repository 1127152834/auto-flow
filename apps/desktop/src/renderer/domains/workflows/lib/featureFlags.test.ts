import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearFlag, isEnabled, setFlag } from './featureFlags'

const KEY = 'autoflow.flags.newStudioLayout'

beforeEach(() => {
  localStorage.clear()
  window.history.replaceState(null, '', '/')
})
afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('featureFlags', () => {
  it('默认关闭', () => {
    expect(isEnabled('newStudioLayout')).toBe(false)
  })

  it.each([['true', true], ['1', true], ['false', false], ['0', false], ['yes', false]])(
    '读取 localStorage 值 %s', (raw, expected) => {
      localStorage.setItem(KEY, raw)
      expect(isEnabled('newStudioLayout')).toBe(expected)
    })

  it('setFlag / clearFlag 读写同一个键', () => {
    setFlag('newStudioLayout', true)
    expect(localStorage.getItem(KEY)).toBe('true')
    expect(isEnabled('newStudioLayout')).toBe(true)
    clearFlag('newStudioLayout')
    expect(localStorage.getItem(KEY)).toBeNull()
    expect(isEnabled('newStudioLayout')).toBe(false)
  })

  it('URL 参数覆盖存储值', () => {
    localStorage.setItem(KEY, 'true')
    window.history.replaceState(null, '', '/?flag.newStudioLayout=0')
    expect(isEnabled('newStudioLayout')).toBe(false)
    localStorage.removeItem(KEY)
    window.history.replaceState(null, '', '/?flag.newStudioLayout=1')
    expect(isEnabled('newStudioLayout')).toBe(true)
  })

  it('环境变量可开启', () => {
    vi.stubEnv('VITE_FLAG_NEW_STUDIO_LAYOUT', '1')
    expect(isEnabled('newStudioLayout')).toBe(true)
  })

  it('URL 优先于环境变量', () => {
    vi.stubEnv('VITE_FLAG_NEW_STUDIO_LAYOUT', '1')
    window.history.replaceState(null, '', '/?flag.newStudioLayout=0')
    expect(isEnabled('newStudioLayout')).toBe(false)
  })

  it('localStorage 读取抛错时回退 false', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    expect(isEnabled('newStudioLayout')).toBe(false)
  })

  it('localStorage 写入抛错时 setFlag 不抛出', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => setFlag('newStudioLayout', true)).not.toThrow()
  })
})
