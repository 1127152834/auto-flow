import { describe, expect, it } from 'vitest'
import { resolveBackendEnvironment, resolvePackagedSidecarPath, resolvePlatformPaths } from './paths'

describe('platform paths', () => {
  it('uses path joining for user data children', () => {
    expect(resolvePlatformPaths('/Users/test/Library/Application Support/AutoFlow')).toEqual({
      userData: '/Users/test/Library/Application Support/AutoFlow',
      logs: '/Users/test/Library/Application Support/AutoFlow/logs',
    })
  })

  it('resolves the packaged sidecar executable by platform', () => {
    expect(resolvePackagedSidecarPath('/app/resources', 'win32')).toBe('/app/resources/sidecar/autoflow-sidecar.exe')
    expect(resolvePackagedSidecarPath('/app/resources', 'darwin')).toBe('/app/resources/sidecar/autoflow-sidecar')
  })

  it('passes the Electron userData directory to the backend', () => {
    expect(resolveBackendEnvironment('/Users/test/Library/Application Support/AutoFlow')).toEqual({
      AUTOFLOW_DATA_DIR: '/Users/test/Library/Application Support/AutoFlow',
    })
  })
})
