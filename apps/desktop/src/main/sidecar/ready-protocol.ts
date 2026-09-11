import { join } from 'node:path'

export type SidecarReady = { apiVersion: 'v1'; instanceId: string; port: number }

export function parseReadyLine(line: string): SidecarReady {
  if (!line.startsWith('AUTOFLOW_READY ')) throw new Error('invalid readiness prefix')
  let value: unknown
  try {
    value = JSON.parse(line.slice('AUTOFLOW_READY '.length))
  } catch {
    throw new Error('invalid readiness payload')
  }
  if (!value || typeof value !== 'object') throw new Error('invalid readiness payload')
  const data = value as Record<string, unknown>
  if (!Number.isInteger(data.port) || Number(data.port) < 1 || Number(data.port) > 65535) {
    throw new Error('invalid port')
  }
  if (data.apiVersion !== 'v1' || typeof data.instanceId !== 'string' || !data.instanceId) {
    throw new Error('invalid instance metadata')
  }
  return { apiVersion: 'v1', instanceId: data.instanceId, port: Number(data.port) }
}

export function packagedSidecarPath(resourcesPath: string, platformName: NodeJS.Platform): string {
  return join(resourcesPath, 'backend', platformName === 'win32' ? 'autoflow-backend.exe' : 'autoflow-backend')
}
