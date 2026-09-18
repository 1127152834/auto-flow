/**
 * Google authorization handover for the desktop host.
 *
 * The renderer never sees a Google secret: the host runs the installed-app PKCE
 * handshake (or reads the picked service-account key) and posts the credential to
 * the sidecar's host-token internal route, which answers with a one-time token.
 */
import { createHash, randomBytes } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import type { AddressInfo } from 'node:net'
import type { GoogleAuthorization } from '../shared/google-sheets'
import type { DesktopResult } from '../shared/settings'

const AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
const TOKEN_URL = 'https://oauth2.googleapis.com/token'
const SHEETS_SCOPE = 'https://www.googleapis.com/auth/spreadsheets'
const GRANTED_SCOPE = `openid email ${SHEETS_SCOPE}`
const ACCOUNT_LABEL_LIMIT = 120
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const DONE_PAGE = '<!doctype html><meta charset="utf-8"><title>AutoFlow</title><p>Google 授权已完成，可以关闭此页面并返回 AutoFlow。'

export class GoogleDesktopError extends Error {
  readonly code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
  }
}

type SenderFrame = object
type InvokeEvent = { sender: { id: number; mainFrame: SenderFrame }; senderFrame: SenderFrame | null }
type SidecarStatus =
  | { state: 'ready'; baseUrl: string; hostToken: string }
  | { state: 'starting' | 'stopped' | 'failed' }

export type LoopbackAuthorization = {
  redirectUri: string
  code: Promise<string>
  close(): Promise<void>
}

export type GoogleDesktopDependencies = {
  allowedSenderId: number
  getSidecarStatus(): SidecarStatus
  /** The host's file picker; `null` means the user cancelled. */
  chooseConfigFile(): Promise<string | null>
  openExternal(url: string): Promise<void>
  request: typeof fetch
  readConfig?(path: string): Promise<string>
  /** Test seam for the loopback listener that receives the authorization code. */
  listen?(state: string): Promise<LoopbackAuthorization>
  timeoutMs?: number
}

export type GoogleConfig =
  | { method: 'service_account'; serviceAccount: { client_email: string; private_key: string; token_uri: string; project_id?: unknown } }
  | { method: 'oauth'; clientId: string; clientSecret: string }

export function pkcePair(): { verifier: string; challenge: string } {
  const verifier = randomBytes(48).toString('base64url')
  return { verifier, challenge: createHash('sha256').update(verifier).digest('base64url') }
}

export function googleConsentUrl(clientId: string, redirectUri: string, challenge: string, state: string): string {
  const query = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: 'code',
    scope: GRANTED_SCOPE,
    access_type: 'offline',
    prompt: 'consent',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
  })
  return `${AUTHORIZATION_URL}?${query.toString()}`
}

/** Only Google's consent page, carrying the PKCE shape this host builds itself. */
export function assertGoogleConsentUrl(value: string): URL {
  let url: URL
  try { url = new URL(value) } catch { throw new GoogleDesktopError('GOOGLE_CONSENT_URL_INVALID', 'Google 授权地址无效。') }
  if (
    url.protocol !== 'https:'
    || url.hostname !== 'accounts.google.com'
    || url.pathname !== '/o/oauth2/v2/auth'
    || url.username
    || url.password
    || url.port
    || url.hash
    || url.searchParams.get('response_type') !== 'code'
    || url.searchParams.get('code_challenge_method') !== 'S256'
    || !url.searchParams.get('code_challenge')
    || !url.searchParams.get('state')
    || !url.searchParams.get('client_id')
  ) throw new GoogleDesktopError('GOOGLE_CONSENT_URL_INVALID', '仅允许打开本应用生成的 Google 登录地址。')
  return url
}

export function parseGoogleConfig(text: string): GoogleConfig {
  let payload: unknown
  try { payload = JSON.parse(text) } catch { throw new GoogleDesktopError('GOOGLE_CONFIG_INVALID', '这个文件不是合法的 Google JSON 配置。') }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new GoogleDesktopError('GOOGLE_CONFIG_INVALID', '这个文件不是合法的 Google JSON 配置。')
  const record = payload as Record<string, unknown>
  if (record.type === 'service_account') {
    const email = record.client_email
    const key = record.private_key
    const uri = record.token_uri ?? TOKEN_URL
    if (typeof email !== 'string' || !email || typeof key !== 'string' || !key) throw new GoogleDesktopError('GOOGLE_CONFIG_INVALID', '服务账号密钥缺少 client_email 或 private_key。')
    if (uri !== TOKEN_URL) throw new GoogleDesktopError('GOOGLE_CONFIG_UNTRUSTED', '服务账号令牌地址不被信任，请使用官方导出的密钥。')
    return { method: 'service_account', serviceAccount: { client_email: email, private_key: key, token_uri: TOKEN_URL, project_id: record.project_id } }
  }
  const installed = record.installed ?? record.web
  if (installed && typeof installed === 'object' && !Array.isArray(installed)) {
    const clientId = (installed as Record<string, unknown>).client_id
    const clientSecret = (installed as Record<string, unknown>).client_secret
    if (typeof clientId === 'string' && clientId && typeof clientSecret === 'string' && clientSecret) {
      return { method: 'oauth', clientId, clientSecret }
    }
  }
  throw new GoogleDesktopError('GOOGLE_CONFIG_INVALID', '配置既不是桌面客户端凭据也不是服务账号密钥。')
}

/** A loopback listener bound to 127.0.0.1 that resolves with the authorization code. */
export async function listenForAuthorizationCode(state: string, timeoutMs = 300_000): Promise<LoopbackAuthorization> {
  let settle: { resolve(code: string): void; reject(error: unknown): void } | undefined
  const code = new Promise<string>((resolve, reject) => { settle = { resolve, reject } })
  // The caller decides when to observe the outcome; an HTTP callback alone must
  // never surface as an unhandled rejection.
  void code.catch(() => undefined)
  const server = createServer((request, response) => {
    const url = new URL(request.url ?? '/', 'http://127.0.0.1')
    if (url.pathname !== '/') { response.writeHead(404).end(); return }
    if (url.searchParams.get('error')) {
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(DONE_PAGE)
      settle?.reject(new GoogleDesktopError('GOOGLE_AUTH_DENIED', 'Google 授权被拒绝或已取消。'))
      return
    }
    // A stray or forged callback must not end the flow; only the real state wins.
    if (url.searchParams.get('state') !== state || !url.searchParams.get('code')) { response.writeHead(400).end(); return }
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(DONE_PAGE)
    settle?.resolve(String(url.searchParams.get('code')))
  })
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => resolve())
  })
  const port = (server.address() as AddressInfo).port
  const timer = setTimeout(() => settle?.reject(new GoogleDesktopError('GOOGLE_AUTH_TIMEOUT', '等待 Google 授权超时，请重新发起连接。')), timeoutMs)
  let closed = false
  return {
    redirectUri: `http://127.0.0.1:${port}/`,
    code,
    close: async () => {
      if (closed) return
      closed = true
      clearTimeout(timer)
      await new Promise<void>(resolve => server.close(() => resolve()))
    },
  }
}

function internalEndpoint(status: Extract<SidecarStatus, { state: 'ready' }>): string {
  let url: URL
  try { url = new URL(status.baseUrl) } catch { throw new GoogleDesktopError('SERVICE_UNAVAILABLE', '本地服务地址无效，请重启 AutoFlow。') }
  if (
    url.protocol !== 'http:'
    || url.hostname !== '127.0.0.1'
    || !url.port
    || url.pathname !== '/'
    || url.username
    || url.password
    || url.search
    || url.hash
    || !status.hostToken
  ) throw new GoogleDesktopError('SERVICE_UNAVAILABLE', '本地服务地址无效，请重启 AutoFlow。')
  return `${url.origin}/internal/google-authorizations`
}

async function exchangeAuthorizationCode(
  request: typeof fetch,
  input: { clientId: string; clientSecret: string; code: string; verifier: string; redirectUri: string },
  timeoutMs: number,
): Promise<{ refreshToken: string; scope: string }> {
  let response: Response
  try {
    response = await request(TOKEN_URL, {
      method: 'POST',
      redirect: 'error',
      signal: AbortSignal.timeout(timeoutMs),
      headers: { accept: 'application/json', 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: input.clientId,
        client_secret: input.clientSecret,
        code: input.code,
        code_verifier: input.verifier,
        redirect_uri: input.redirectUri,
        grant_type: 'authorization_code',
      }).toString(),
    })
  } catch {
    throw new GoogleDesktopError('GOOGLE_UNREACHABLE', 'Google 授权服务当前不可达，请检查网络后重试。')
  }
  if (!response.ok) throw new GoogleDesktopError('GOOGLE_AUTH_REJECTED', `Google 拒绝了本次授权（HTTP ${response.status}）。`)
  let payload: unknown
  try { payload = await response.json() } catch { throw new GoogleDesktopError('GOOGLE_AUTH_INVALID', 'Google 返回了无法解析的授权响应。') }
  const record = (payload ?? {}) as Record<string, unknown>
  if (typeof record.refresh_token !== 'string' || !record.refresh_token) throw new GoogleDesktopError('GOOGLE_AUTH_REJECTED', '授权未返回长期凭据，请重新授权并确认离线访问。')
  return { refreshToken: record.refresh_token, scope: typeof record.scope === 'string' && record.scope ? record.scope : GRANTED_SCOPE }
}

async function registerAuthorization(
  request: typeof fetch,
  status: Extract<SidecarStatus, { state: 'ready' }>,
  body: Record<string, unknown>,
  timeoutMs: number,
): Promise<GoogleAuthorization> {
  let response: Response
  try {
    response = await request(internalEndpoint(status), {
      method: 'POST',
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(timeoutMs),
      headers: {
        accept: 'application/json',
        'content-type': 'application/json',
        'x-autoflow-host-token': status.hostToken,
      },
      body: JSON.stringify(body),
    })
  } catch {
    throw new GoogleDesktopError('GOOGLE_REGISTRATION_FAILED', '本地服务未能登记这次 Google 授权，请重试。')
  }
  if (!response.ok) throw new GoogleDesktopError('GOOGLE_REGISTRATION_FAILED', `本地服务拒绝了这次 Google 授权（HTTP ${response.status}）。`)
  let payload: unknown
  try { payload = await response.json() } catch { throw new GoogleDesktopError('GOOGLE_REGISTRATION_FAILED', '本地服务返回了无法解析的授权响应。') }
  const record = (payload ?? {}) as Record<string, unknown>
  if (typeof record.authorizationToken !== 'string' || !record.authorizationToken || typeof record.accountLabel !== 'string' || typeof record.writable !== 'boolean') {
    throw new GoogleDesktopError('GOOGLE_REGISTRATION_FAILED', '本地服务返回了不完整的授权响应。')
  }
  return { authorizationToken: record.authorizationToken, accountLabel: record.accountLabel, writable: record.writable }
}

export function createConnectGoogleSheetsHandler(dependencies: GoogleDesktopDependencies) {
  const timeoutMs = dependencies.timeoutMs ?? 30_000
  const readConfig = dependencies.readConfig ?? ((path: string) => readFile(path, 'utf8'))
  const listen = dependencies.listen ?? ((state: string) => listenForAuthorizationCode(state, timeoutMs * 10))

  const authorizeInstalledApp = async (client: { clientId: string; clientSecret: string }) => {
    const state = randomBytes(24).toString('base64url')
    const { verifier, challenge } = pkcePair()
    const loopback = await listen(state)
    try {
      await dependencies.openExternal(assertGoogleConsentUrl(googleConsentUrl(client.clientId, loopback.redirectUri, challenge, state)).href)
      const code = await loopback.code
      return await exchangeAuthorizationCode(
        dependencies.request,
        { clientId: client.clientId, clientSecret: client.clientSecret, code, verifier, redirectUri: loopback.redirectUri },
        timeoutMs,
      )
    } finally {
      await loopback.close()
    }
  }

  return async (event: InvokeEvent, projectId: unknown, accountLabel: unknown): Promise<DesktopResult<GoogleAuthorization | null>> => {
    if (event.sender.id !== dependencies.allowedSenderId || event.senderFrame === null || event.senderFrame !== event.sender.mainFrame) {
      return { ok: false, error: { code: 'UNAUTHORIZED_WINDOW', message: '当前窗口不能连接 Google 账号。' } }
    }
    if (typeof projectId !== 'string' || !UUID.test(projectId)) {
      return { ok: false, error: { code: 'INVALID_PROJECT', message: '项目标识无效，请重新加载页面。' } }
    }
    const label = typeof accountLabel === 'string' ? accountLabel.trim() : ''
    if (!label || label.length > ACCOUNT_LABEL_LIMIT) {
      return { ok: false, error: { code: 'GOOGLE_ACCOUNT_LABEL_INVALID', message: `账号名称必须为 1–${ACCOUNT_LABEL_LIMIT} 个字符。` } }
    }
    const status = dependencies.getSidecarStatus()
    if (status.state !== 'ready') return { ok: false, error: { code: 'SERVICE_UNAVAILABLE', message: '本地服务尚未就绪，请稍后再试。' } }
    try {
      const path = await dependencies.chooseConfigFile()
      if (!path) return { ok: true, value: null }
      const config = parseGoogleConfig(await readConfig(path))
      let credential: Record<string, unknown>
      if (config.method === 'service_account') {
        credential = { authMethod: 'service_account', accountLabel: label, grantedScope: SHEETS_SCOPE, serviceAccount: config.serviceAccount }
      } else {
        const token = await authorizeInstalledApp(config)
        credential = {
          authMethod: 'oauth',
          accountLabel: label,
          grantedScope: token.scope,
          refreshToken: token.refreshToken,
          clientId: config.clientId,
          clientSecret: config.clientSecret,
        }
      }
      const value = await registerAuthorization(
        dependencies.request,
        status,
        { projectId, accountLabel: label, authMethod: config.method, credential },
        timeoutMs,
      )
      return { ok: true, value }
    } catch (error) {
      if (error instanceof GoogleDesktopError) return { ok: false, error: { code: error.code, message: error.message } }
      return { ok: false, error: { code: 'GOOGLE_AUTHORIZATION_FAILED', message: 'Google 授权未完成，请重试。' } }
    }
  }
}
