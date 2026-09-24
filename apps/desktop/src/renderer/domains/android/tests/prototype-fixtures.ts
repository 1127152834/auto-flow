import type { AndroidDevice, AndroidEnvironment } from '../api'
import type { Allocation, ConsoleSession, DeviceRun, Profile } from '../fleet-api'
import one from '../assets/reference/board-device-01.png'
import two from '../assets/reference/board-device-02.png'
import three from '../assets/reference/board-device-03.png'
import four from '../assets/reference/board-device-04.png'
import five from '../assets/reference/board-device-05.png'
import six from '../assets/reference/board-device-06.png'
export const profile: Profile = {
  id: '00000000-0000-4000-8000-000000000010',
  revision: 1,
  name: 'Android 13 标准 · ARM64',
  imageId: 'sha256:' + 'a'.repeat(64),
  width: 720,
  height: 1280,
  dpi: 320,
  cpu: 1,
  memoryMb: 1536,
  locale: 'zh-CN',
  timezone: 'Asia/Shanghai',
  shellRoot: 'available',
  applicationRoot: 'unknown',
  archived: false,
}
export const devices: AndroidDevice[] = [
  '测试设备 01',
  '测试设备 02',
  '订单回归 03',
  '应用测试 04',
  '临时设备 05',
  '测试设备 06',
].map((name, index) => ({
  deviceId: `00000000-0000-4000-8000-00000000000${index + 1}`,
  name,
  runtimeId: 'lima',
  ownerRunId: index === 2 || index === 3 ? `run-${index}` : null,
  control: index === 2 || index === 3 ? 'workflow' : index === 4 ? 'managing' : 'idle',
  generation: 1,
  width: index === 4 ? 540 : 720,
  height: index === 4 ? 960 : 1280,
  imageId: profile.imageId,
  androidStatus: index === 4 ? 'starting' : index === 5 ? 'stopped' : 'ready',
  lastError: null,
  cpu: 1,
  memoryMb: 1536,
  dpi: 320,
  androidVersion: '13',
  architecture: 'arm64',
  dataRetained: false,
  deleted: false,
  profileId: profile.id,
  profileName: index === 3 ? 'Android 13 · Magisk' : profile.name,
  instanceType: index === 2 || index === 4 ? 'temporary' : 'persistent',
  locale: 'zh-CN',
  timezone: 'Asia/Shanghai',
}))
export const images = Object.fromEntries(devices.map((d, i) => [d.deviceId, [one, two, three, four, five, six][i]]))
export const environment: AndroidEnvironment = {
  available: true,
  platformSupported: true,
  runtimeId: 'lima',
  message: '运行环境可用',
  images: [{ id: profile.imageId, name: profile.name, reference: 'pinned' }],
  cpuCount: 6,
  memoryMb: 8000,
}
export const runs: Record<string, DeviceRun> = {
  [devices[2].deviceId]: {
    runId: 'run-2',
    workflowName: '订单回归',
    state: 'running',
    currentNodeId: 'n3',
    currentStep: 3,
    totalSteps: 6,
    startedAt: '2026-09-13T08:00:00Z',
    steps: [
      { id: 'n1', label: '准备设备' },
      { id: 'n2', label: '启动应用' },
      { id: 'n3', label: '验证订单列表' },
      { id: 'n4', label: '保存截图' },
      { id: 'n5', label: '验证订单详情' },
      { id: 'n6', label: '完成' },
    ],
    handoff: null,
  },
  [devices[3].deviceId]: {
    runId: 'run-3',
    workflowName: 'APK 回归',
    state: 'running',
    currentNodeId: 'n2',
    currentStep: 2,
    totalSteps: 4,
    startedAt: '2026-09-13T08:00:00Z',
    steps: [
      { id: 'n1', label: '启动应用' },
      { id: 'n2', label: '检查启动结果' },
    ],
    handoff: null,
  },
}
export const allocations: Allocation[] = ['登录回归', '通知验证'].map((workflowName, i) => ({
  id: `queue-${i}`,
  createdAt: '2026-09-13T08:00:00Z',
  state: i ? 'waiting_start' : 'waiting_create',
  workflowName,
  profileName: 'Android 13 标准',
  deviceId: i ? devices[5].deviceId : null,
  deviceName: i ? devices[5].name : null,
  runId: null,
  error: null,
  request: {
    requestId: `queue-${i}`,
    workflowId: `workflow-${i}`,
    profileId: profile.id,
    mode: i ? 'specified' : 'temporary',
    deviceId: i ? devices[5].deviceId : null,
    values: {},
  },
}))
export function fixtureSession(manual: boolean): ConsoleSession {
  return {
    id: 'fixture',
    deviceId: devices[manual ? 0 : 2].deviceId,
    generation: 1,
    access: manual ? 'manual' : 'readonly',
    endpoint: 'embedded',
    state: 'connected',
    width: 720,
    height: 1280,
    latestOperation: '文本已发送 · 刚刚',
  }
}
