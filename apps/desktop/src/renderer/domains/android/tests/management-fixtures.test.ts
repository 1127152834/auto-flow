import { expect, it } from 'vitest'
import { DEVICE_ID, PROFILE_ID, makeDevice, makeSession, makeApi } from './management-fixtures'

it('exports distinct stable identifiers and independent device sessions', () => {
  expect(DEVICE_ID).not.toBe(PROFILE_ID)
  expect(makeDevice().deviceId).toBe(DEVICE_ID)
  expect(makeSession().deviceId).toBe(DEVICE_ID)
})

it('rejects unknown write requests instead of pretending success', async () => {
  await expect(makeApi().request('/unknown', { method: 'POST' })).rejects.toThrow('unsupported')
})
