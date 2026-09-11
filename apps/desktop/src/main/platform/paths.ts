export type PlatformPaths = { userData: string; logs: string }

export function resolvePlatformPaths(userData: string): PlatformPaths {
  return { userData, logs: `${userData}/logs` }
}
