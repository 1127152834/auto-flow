import { join } from 'node:path'
import { packagedSidecarPath } from '../sidecar/ready-protocol'

export type PlatformPaths = { userData: string; logs: string }
export type BackendEnvironment = { AUTOFLOW_DATA_DIR: string }

export function resolvePlatformPaths(userData: string): PlatformPaths {
  return { userData, logs: join(userData, 'logs') }
}

export function resolveBackendEnvironment(userData: string): BackendEnvironment {
  return { AUTOFLOW_DATA_DIR: userData }
}

export function resolvePackagedSidecarPath(resourcesPath: string, platformName: NodeJS.Platform): string {
  return packagedSidecarPath(resourcesPath, platformName)
}
