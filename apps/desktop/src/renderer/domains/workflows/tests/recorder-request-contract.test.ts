import { expect, it, vi } from 'vitest'
import { recorderApi } from '../api'
import { configureStudioConnection } from '../api/config'

it.each(['', ' ', undefined, 3])('rejects invalid session %j before sending any recorder command', async session => {
  const fetcher = vi.fn(async () => Response.json({ success: true }))
  const restore = configureStudioConnection('http://recorder.fixture', fetcher)
  try {
    expect((await recorderApi.start(session as string)).success).toBe(false)
    expect((await recorderApi.stop(session as string)).success).toBe(false)
    expect((await recorderApi.events(session as string)).success).toBe(false)
    expect(fetcher).not.toHaveBeenCalled()
  } finally { restore() }
})
it.each([-1, 1.5, '1', true, Number.MAX_SAFE_INTEGER + 1])('rejects invalid cursor %j before read or stop', async cursor => {
  const fetcher = vi.fn(async () => Response.json({ success: true }))
  const restore = configureStudioConnection('http://recorder.fixture', fetcher)
  try {
    expect((await recorderApi.stop('session', cursor as number)).success).toBe(false)
    expect((await recorderApi.events('session', cursor as number)).success).toBe(false)
    expect(fetcher).not.toHaveBeenCalled()
  } finally { restore() }
})
