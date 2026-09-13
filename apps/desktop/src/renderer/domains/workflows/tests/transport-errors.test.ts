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
    await expect(studioFetch(new Request('http://autoflow-studio.mock/save', { signal: controller.signal }))).rejects.toThrow()
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
it('announces recovery once after a subsequent successful request, excluding older requests and HTTP errors', async () => {
  const recovered = vi.fn()
  window.addEventListener('studio:connection-restored', recovered)
  let old!: (value: Response) => void
  let mode: 'pending' | 'offline' | 'error' | 'ok' = 'pending'
  const restore = setStudioTransport(async () => {
    if (mode === 'pending') return new Promise(resolve => { old = resolve })
    if (mode === 'offline') throw new TypeError('Failed to fetch')
    return new Response(null, { status: mode === 'error' ? 503 : 200 })
  })
  try {
    const previous = studioFetch('/old')
    mode = 'offline'; await expect(studioFetch('/now')).rejects.toThrow()
    old(new Response()); await previous
    expect(recovered).not.toHaveBeenCalled()
    mode = 'error'; await studioFetch('/now')
    expect(recovered).not.toHaveBeenCalled()
    mode = 'ok'; await studioFetch('/now'); await studioFetch('/again')
    expect(recovered).toHaveBeenCalledOnce()
  } finally { restore(); window.removeEventListener('studio:connection-restored', recovered) }
})
it('does not report a late network error from a replaced transport', async () => {
  const failure = vi.fn()
  window.addEventListener('studio:connection-error', failure)
  let reject!: (error: Error) => void
  const restore = setStudioTransport(() => new Promise((_resolve, fail) => { reject = fail }))
  const old = studioFetch('/old')
  const observed = expect(old).rejects.toThrow('Failed to fetch')
  const restoreNew = setStudioTransport(async () => new Response())
  try {
    await studioFetch('/new')
    reject(new TypeError('Failed to fetch')); await observed
    expect(failure).not.toHaveBeenCalled()
  } finally { restoreNew(); restore(); window.removeEventListener('studio:connection-error', failure) }
})
