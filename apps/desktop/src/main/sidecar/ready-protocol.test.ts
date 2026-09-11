import { describe, expect, it } from 'vitest'
import { parseReadyLine } from './ready-protocol'

describe('parseReadyLine', () => {
  it('parses the backend readiness line', () => {
    expect(parseReadyLine('AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":43127}')).toEqual({ apiVersion: 'v1', instanceId: 'x', port: 43127 })
  })
  it('rejects a readiness line with an invalid port', () => {
    expect(() => parseReadyLine('AUTOFLOW_READY {"apiVersion":"v1","instanceId":"x","port":-1}')).toThrow('invalid port')
  })
})
