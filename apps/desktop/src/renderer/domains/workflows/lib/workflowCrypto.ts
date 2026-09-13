// Source: WebRPA@5ccb900e, lib/workflowCrypto.ts; see SOURCE.md for license and adaptation boundaries.
/**
 * 工作流加密分享：用密码对工作流 JSON 做 AES-GCM 加密，生成可安全分享的加密包。
 * 接收方导入时输入同一密码即可解密还原。基于浏览器原生 Web Crypto，无第三方依赖。
 */

const ENC_MAGIC = 'webrpa-encrypted-workflow'
const ENC_VERSION = 1

export interface EncryptedEnvelope {
  __webrpa_encrypted: string // = ENC_MAGIC
  version: number
  salt: string // base64
  iv: string // base64
  data: string // base64 密文
  name?: string // 明文工作流名（便于导入前识别，不含敏感内容）
}

function bufToB64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf)
  let s = ''
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i])
  return btoa(s)
}
function b64ToBuf(b64: string): Uint8Array {
  const s = atob(b64)
  const bytes = new Uint8Array(s.length)
  for (let i = 0; i < s.length; i++) bytes[i] = s.charCodeAt(i)
  return bytes
}

async function deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
  const enc = new TextEncoder()
  const baseKey = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey'])
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: salt as BufferSource, iterations: 150000, hash: 'SHA-256' },
    baseKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  )
}

/** 加密工作流 JSON 字符串，返回加密信封对象 */
export async function encryptWorkflow(jsonStr: string, password: string, name?: string): Promise<EncryptedEnvelope> {
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const key = await deriveKey(password, salt)
  const enc = new TextEncoder()
  const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv as BufferSource }, key, enc.encode(jsonStr) as BufferSource)
  return {
    __webrpa_encrypted: ENC_MAGIC,
    version: ENC_VERSION,
    salt: bufToB64(salt.buffer),
    iv: bufToB64(iv.buffer),
    data: bufToB64(cipher),
    name,
  }
}

/** 判断对象是否为 WebRPA 加密信封 */
export function isEncryptedEnvelope(obj: any): obj is EncryptedEnvelope {
  return !!obj && obj.__webrpa_encrypted === ENC_MAGIC && typeof obj.data === 'string'
}

/** 解密加密信封，返回工作流 JSON 字符串；密码错误会抛出异常 */
export async function decryptWorkflow(env: EncryptedEnvelope, password: string): Promise<string> {
  const salt = b64ToBuf(env.salt)
  const iv = b64ToBuf(env.iv)
  const key = await deriveKey(password, salt)
  const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv as BufferSource }, key, b64ToBuf(env.data) as BufferSource)
  return new TextDecoder().decode(plain)
}
