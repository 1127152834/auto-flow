import { join } from 'node:path'

export type PlatformPaths = { userData: string; logs: string }

export function resolvePlatformPaths(userData: string): PlatformPaths {
  return { userData, logs: join(userData, 'logs') }
}

export function resolvePackagedSidecarPath(resourcesPath: string, platformName: NodeJS.Platform): string {
  return join(resourcesPath, 'sidecar', platformName === 'win32' ? 'autoflow-sidecar.exe' : 'autoflow-sidecar')
}
