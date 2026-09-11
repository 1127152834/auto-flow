import { describe, expect, it } from 'vitest'
import { applySidecarEvent, initialSidecarStatus } from './supervisor'

describe('sidecar status transitions', () => {
  it('only exposes a ready status after a valid ready event', () => {
    const starting = applySidecarEvent(initialSidecarStatus(), { type: 'spawned' })
    expect(starting).toEqual({ state: 'starting' })
    expect(applySidecarEvent(starting, { type: 'ready', apiVersion: 'v1', instanceId: 'x', port: 43127, baseUrl: 'http://127.0.0.1:43127', token: 'secret' })).toEqual({ state: 'ready', apiVersion: 'v1', instanceId: 'x', port: 43127, baseUrl: 'http://127.0.0.1:43127', token: 'secret' })
  })
})
