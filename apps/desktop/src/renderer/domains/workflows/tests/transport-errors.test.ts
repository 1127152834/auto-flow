import { expect, it, vi } from 'vitest'
import { setStudioTransport, studioFetch } from '../api/transport'

it('notifies for each network failure including direct callers, but not intentional cancellation', async () => {
  const listener = vi.fn()
  window.addEventListener('studio:connection-error', listener)
  const restore = setStudioTransport(async () => { throw new TypeError('Failed to fetch') })
  try {
    await expect(studioFetch('/save')).rejects.toThrow('Failed to fetch')
    await expect(studioFetch('/save')).rejects.toThrow('Failed to fetch')
    expect(listener).toHaveBeenCalledTimes(2)
    const controller = new AbortController()
    controller.abort()
    await expect(studioFetch('/save', { signal: controller.signal })).rejects.toThrow()
    expect(listener).toHaveBeenCalledTimes(2)
  } finally { restore(); window.removeEventListener('studio:connection-error', listener) }
})

it('preserves HTTP business failures without labelling them as connection outages', async () => {
  const listener = vi.fn()
  window.addEventListener('studio:connection-error', listener)
  const restore = setStudioTransport(async () => new Response('conflict', { status: 409 }))
  try {
    expect((await studioFetch('/save')).status).toBe(409)
    expect(listener).not.toHaveBeenCalled()
  } finally { restore(); window.removeEventListener('studio:connection-error', listener) }
})
