import type { StreamingApiClient } from '../../../shared/api/client'
import type { AndroidDevice, AndroidEnvironment } from '../api'
import type { ConsoleSession } from '../fleet-api'

export const DEVICE_ID = '11111111-1111-4111-8111-111111111111'
export const PROFILE_ID = '22222222-2222-4222-8222-222222222222'

export function makeDevice(overrides: Partial<AndroidDevice> = {}): AndroidDevice {
  return {
    deviceId: DEVICE_ID,
    name: '测试设备',
    runtimeId: 'lima',
    ownerRunId: null,
    control: 'idle',
    generation: 1,
    width: 720,
    height: 1280,
    imageId: 'sha256:' + 'a'.repeat(64),
    androidStatus: 'ready',
    lastError: null,
    cpu: 1,
    memoryMb: 1536,
    dpi: 320,
    androidVersion: '13',
    architecture: 'arm64',
    dataRetained: false,
    deleted: false,
    profileId: PROFILE_ID,
    profileName: 'Android 13 标准 · ARM64',
    instanceType: 'persistent',
    locale: 'zh-CN',
    timezone: 'Asia/Shanghai',
    ...overrides,
  }
}

export function makeSession(overrides: Partial<ConsoleSession> = {}): ConsoleSession {
  return {
    id: '33333333-3333-4333-8333-333333333333',
    deviceId: DEVICE_ID,
    generation: 1,
    access: 'manual',
    endpoint: 'embedded',
    state: 'connected',
    width: 720,
    height: 1280,
    latestOperation: null,
    ...overrides,
  }
}

export function makeApi(): StreamingApiClient {
  return {
    request: async <T>(path: string): Promise<T> => {
      if (path.endsWith('/devices')) return [makeDevice()] as T
      if (path.endsWith('/environment')) return { available: true, platformSupported: true, runtimeId: 'lima', message: '可用', images: [], cpuCount: 4, memoryMb: 4096 } satisfies AndroidEnvironment as T
      throw new Error(`unsupported fixture request: ${path}`)
    },
    stream: async () => new Response(new Blob()),
    health: async () => ({ status: 'ok' }),
  }
}
