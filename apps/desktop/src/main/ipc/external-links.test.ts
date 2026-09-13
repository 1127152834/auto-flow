// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'
import { createOpenExternalLinkHandler } from './external-links'
import { validatedExternalUrl } from '../../shared/external-links'

const frame = {}, event = { sender: { id: 7, mainFrame: frame }, senderFrame: frame }
describe('controlled record external links', () => {
  it.each(['file:///tmp/private', 'javascript:alert(1)', 'data:text/plain,x', '/relative', '//example.com', 'https://user:secret@example.com', 'https://example.com/with space', 'https://example.com/\n', '', null])('rejects invalid target %s before opening', async raw => {
    const openExternal = vi.fn()
    const result = await createOpenExternalLinkHandler({ allowedSenderId: 7, openExternal })(event, raw)
    expect(result).toMatchObject({ ok: false, error: { code: 'INVALID_EXTERNAL_LINK' } })
    expect(openExternal).not.toHaveBeenCalled()
  })
  it('rejects strangers, child frames and absent frames', async () => {
    const openExternal = vi.fn()
    const handler = createOpenExternalLinkHandler({ allowedSenderId: 7, openExternal })
    for (const value of [{ ...event, sender: { ...event.sender, id: 8 } }, { ...event, senderFrame: {} }, { ...event, senderFrame: null }]) {
      expect(await handler(value, 'https://example.com')).toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
    }
    expect(openExternal).not.toHaveBeenCalled()
  })
  it('opens only a validated URL and confirms after the OS accepts it', async () => {
    const openExternal = vi.fn(async () => {})
    expect(await createOpenExternalLinkHandler({ allowedSenderId: 7, openExternal })(event, 'https://example.com/资料?q=1')).toEqual({ ok: true, value: { opened: true } })
    expect(openExternal).toHaveBeenCalledExactlyOnceWith('https://example.com/%E8%B5%84%E6%96%99?q=1')
    expect(validatedExternalUrl('http://127.0.0.1:1234/')).toBe('http://127.0.0.1:1234/')
  })
  it('does not expose OS exception details or claim success on rejection', async () => {
    const handler = createOpenExternalLinkHandler({ allowedSenderId: 7, openExternal: async () => { throw Error('/private/account-secret') } })
    const result = await handler(event, 'https://example.com')
    expect(result).toMatchObject({ ok: false, error: { code: 'EXTERNAL_LINK_FAILED' } })
    expect(JSON.stringify(result)).not.toContain('account-secret')
  })
})
