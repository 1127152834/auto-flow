// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'
import {
  assertGoogleConsentUrl,
  createConnectGoogleSheetsHandler,
  listenForAuthorizationCode,
  parseGoogleConfig,
  type GoogleDesktopDependencies,
} from './google-desktop'

const PROJECT = '3f9a1f7a-6c1f-4e6a-9bdc-1f2f0a7d4c11'
const frame = {}, event = { sender: { id: 7, mainFrame: frame }, senderFrame: frame }
const ready = { state: 'ready', baseUrl: 'http://127.0.0.1:4567', hostToken: 'host-token' } as const
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })

const SERVICE_ACCOUNT = JSON.stringify({ type: 'service_account', client_email: 'bot@example.iam.gserviceaccount.com', private_key: '-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----\n', token_uri: 'https://oauth2.googleapis.com/token', project_id: 'demo' })
const INSTALLED_APP = JSON.stringify({ installed: { client_id: 'client.apps.googleusercontent.com', client_secret: 'client-secret', redirect_uris: ['http://localhost'] } })

function dependencies(overrides: Partial<GoogleDesktopDependencies> = {}): GoogleDesktopDependencies {
  return {
    allowedSenderId: 7,
    getSidecarStatus: () => ready,
    chooseConfigFile: async () => '/tmp/config.json',
    openExternal: async () => {},
    request: (async () => json({ authorizationToken: 'one-time', accountLabel: '运营账号', writable: true })) as unknown as typeof fetch,
    readConfig: async () => SERVICE_ACCOUNT,
    ...overrides,
  }
}

describe('google authorization handover', () => {
  it('refuses strangers, child frames and absent frames before touching the picker', async () => {
    const chooseConfigFile = vi.fn(async () => '/tmp/config.json')
    const handler = createConnectGoogleSheetsHandler(dependencies({ chooseConfigFile }))
    for (const value of [{ ...event, sender: { ...event.sender, id: 8 } }, { ...event, senderFrame: {} }, { ...event, senderFrame: null }]) {
      expect(await handler(value, PROJECT, '运营账号')).toMatchObject({ ok: false, error: { code: 'UNAUTHORIZED_WINDOW' } })
    }
    expect(chooseConfigFile).not.toHaveBeenCalled()
  })

  it('rejects an unusable project id or account label and an unavailable service', async () => {
    const handler = createConnectGoogleSheetsHandler(dependencies())
    expect(await handler(event, 'not-a-uuid', '运营账号')).toMatchObject({ ok: false, error: { code: 'INVALID_PROJECT' } })
    expect(await handler(event, PROJECT, '   ')).toMatchObject({ ok: false, error: { code: 'GOOGLE_ACCOUNT_LABEL_INVALID' } })
    expect(await handler(event, PROJECT, 'x'.repeat(121))).toMatchObject({ ok: false, error: { code: 'GOOGLE_ACCOUNT_LABEL_INVALID' } })
    const stopped = createConnectGoogleSheetsHandler(dependencies({ getSidecarStatus: () => ({ state: 'stopped' }) }))
    expect(await stopped(event, PROJECT, '运营账号')).toMatchObject({ ok: false, error: { code: 'SERVICE_UNAVAILABLE' } })
  })

  it('treats a cancelled file choice as a successful no-op', async () => {
    const request = vi.fn()
    const handler = createConnectGoogleSheetsHandler(dependencies({ chooseConfigFile: async () => null, request: request as unknown as typeof fetch }))
    expect(await handler(event, PROJECT, '运营账号')).toEqual({ ok: true, value: null })
    expect(request).not.toHaveBeenCalled()
  })

  it('registers a service account credential through the host-token route only', async () => {
    const request = vi.fn(async () => json({ authorizationToken: 'one-time', accountLabel: '运营账号', writable: true }))
    const result = await createConnectGoogleSheetsHandler(dependencies({ request: request as unknown as typeof fetch }))(event, PROJECT, ' 运营账号 ')
    expect(result).toEqual({ ok: true, value: { authorizationToken: 'one-time', accountLabel: '运营账号', writable: true } })
    const [url, init] = request.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('http://127.0.0.1:4567/internal/google-authorizations')
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>)['x-autoflow-host-token']).toBe('host-token')
    const body = JSON.parse(String(init.body)) as { projectId: string; accountLabel: string; authMethod: string; credential: { serviceAccount: { client_email: string; token_uri: string } } }
    expect(body.projectId).toBe(PROJECT)
    expect(body.accountLabel).toBe('运营账号')
    expect(body.authMethod).toBe('service_account')
    expect(body.credential.serviceAccount.client_email).toBe('bot@example.iam.gserviceaccount.com')
    expect(body.credential.serviceAccount.token_uri).toBe('https://oauth2.googleapis.com/token')
  })

  it.each([
    ['not json', 'GOOGLE_CONFIG_INVALID'],
    ['[]', 'GOOGLE_CONFIG_INVALID'],
    ['{"type":"service_account","client_email":"a@b","private_key":"k","token_uri":"https://evil.example.com/token"}', 'GOOGLE_CONFIG_UNTRUSTED'],
    ['{"installed":{"client_id":"x"}}', 'GOOGLE_CONFIG_INVALID'],
  ])('refuses unusable configuration %s', async (text, code) => {
    const request = vi.fn()
    const handler = createConnectGoogleSheetsHandler(dependencies({ readConfig: async () => text, request: request as unknown as typeof fetch }))
    expect(await handler(event, PROJECT, '账号')).toMatchObject({ ok: false, error: { code } })
    expect(request).not.toHaveBeenCalled()
  })

  it('runs the installed-app PKCE handshake and keeps secrets out of the result', async () => {
    const close = vi.fn(async () => {})
    const listen = vi.fn(async (_state: string) => ({ redirectUri: 'http://127.0.0.1:3210/', code: Promise.resolve('auth-code'), close }))
    const openExternal = vi.fn(async (_url: string) => {})
    const request = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url) === 'https://oauth2.googleapis.com/token') {
        const form = new URLSearchParams(String(init?.body))
        expect(form.get('code')).toBe('auth-code')
        expect(form.get('grant_type')).toBe('authorization_code')
        expect(form.get('redirect_uri')).toBe('http://127.0.0.1:3210/')
        expect(form.get('code_verifier')).toBeTruthy()
        return json({ refresh_token: 'refresh-token', scope: 'openid email https://www.googleapis.com/auth/spreadsheets' })
      }
      return json({ authorizationToken: 'one-time', accountLabel: '运营账号', writable: true })
    })
    const handler = createConnectGoogleSheetsHandler(dependencies({ readConfig: async () => INSTALLED_APP, listen, openExternal, request: request as unknown as typeof fetch }))
    const result = await handler(event, PROJECT, '运营账号')
    expect(result).toEqual({ ok: true, value: { authorizationToken: 'one-time', accountLabel: '运营账号', writable: true } })
    expect(JSON.stringify(result)).not.toContain('client-secret')
    expect(JSON.stringify(result)).not.toContain('refresh-token')

    const opened = assertGoogleConsentUrl(String(openExternal.mock.calls[0]?.[0]))
    expect(opened.searchParams.get('response_type')).toBe('code')
    expect(opened.searchParams.get('code_challenge_method')).toBe('S256')
    expect(opened.searchParams.get('scope')).toContain('https://www.googleapis.com/auth/spreadsheets')
    expect(opened.searchParams.get('access_type')).toBe('offline')
    expect(listen.mock.calls[0]?.[0]).toBe(opened.searchParams.get('state'))

    const [, register] = request.mock.calls[1] as unknown as [string, RequestInit]
    const body = JSON.parse(String(register.body)) as { authMethod: string; credential: Record<string, string> }
    expect(body.authMethod).toBe('oauth')
    expect(body.credential.refreshToken).toBe('refresh-token')
    expect(body.credential.clientId).toBe('client.apps.googleusercontent.com')
    expect(close).toHaveBeenCalledOnce()
  })

  it('closes the loopback listener and reports a refusal without leaking the reason', async () => {
    const close = vi.fn(async () => {})
    const listen = async () => ({ redirectUri: 'http://127.0.0.1:3210/', code: Promise.reject(Object.assign(new Error('denied by user'), { code: 'GOOGLE_AUTH_DENIED' })), close })
    const handler = createConnectGoogleSheetsHandler(dependencies({ readConfig: async () => INSTALLED_APP, listen }))
    const result = await handler(event, PROJECT, '运营账号')
    expect(result).toMatchObject({ ok: false, error: { code: 'GOOGLE_AUTHORIZATION_FAILED' } })
    expect(close).toHaveBeenCalledOnce()
  })

  it('only opens URLs built for Google consent', () => {
    expect(() => assertGoogleConsentUrl('https://evil.example.com/o/oauth2/v2/auth?response_type=code&state=s&code_challenge=c&code_challenge_method=S256&client_id=i')).toThrowError(/仅允许/)
    expect(() => assertGoogleConsentUrl('http://accounts.google.com/o/oauth2/v2/auth?response_type=code&state=s&code_challenge=c&code_challenge_method=S256&client_id=i')).toThrowError(/仅允许/)
    expect(() => assertGoogleConsentUrl('https://accounts.google.com/o/oauth2/v2/auth?response_type=token&state=s')).toThrowError(/仅允许/)
  })

  it('parses both official configuration shapes', () => {
    expect(parseGoogleConfig(SERVICE_ACCOUNT)).toMatchObject({ method: 'service_account' })
    expect(parseGoogleConfig(INSTALLED_APP)).toEqual({ method: 'oauth', clientId: 'client.apps.googleusercontent.com', clientSecret: 'client-secret' })
    expect(parseGoogleConfig('{"web":{"client_id":"a","client_secret":"b"}}')).toEqual({ method: 'oauth', clientId: 'a', clientSecret: 'b' })
  })

  it('waits for the matching state and ignores forged callbacks', async () => {
    const loopback = await listenForAuthorizationCode('expected-state', 2_000)
    const port = new URL(loopback.redirectUri).port
    try {
      expect((await fetch(`http://127.0.0.1:${port}/?code=forged&state=other`)).status).toBe(400)
      expect((await fetch(`http://127.0.0.1:${port}/favicon.ico`)).status).toBe(404)
      const answered = await fetch(`http://127.0.0.1:${port}/?code=real&state=expected-state`)
      expect(answered.status).toBe(200)
      await expect(loopback.code).resolves.toBe('real')
    } finally {
      await loopback.close()
    }
  })

  it('ends the loopback wait when Google reports a refusal', async () => {
    const loopback = await listenForAuthorizationCode('expected-state', 2_000)
    const port = new URL(loopback.redirectUri).port
    try {
      await fetch(`http://127.0.0.1:${port}/?error=access_denied&state=expected-state`)
      await expect(loopback.code).rejects.toMatchObject({ code: 'GOOGLE_AUTH_DENIED' })
    } finally {
      await loopback.close()
    }
  })
})
