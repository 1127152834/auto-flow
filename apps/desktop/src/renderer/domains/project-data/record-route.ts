import type { RecordKey } from './records-api'

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

function validUnicode(value: string) {
  for (let index = 0; index < value.length; index++) {
    const unit = value.charCodeAt(index)
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(++index)
      if (!(next >= 0xdc00 && next <= 0xdfff)) throw new Error('记录键包含无效 Unicode 字符')
    } else if (unit >= 0xdc00 && unit <= 0xdfff) throw new Error('记录键包含无效 Unicode 字符')
  }
}

function validateRecordKey(key: RecordKey): RecordKey {
  validUnicode(key.value)
  if (key.type === 'text') {
    const length = Array.from(key.value).length
    if (length === 0 || length > 8000) throw new Error('文本记录键长度无效')
  } else if (key.type === 'integer') {
    if (!/^(?:0|-[1-9]\d*|[1-9]\d*)$/.test(key.value) || !Number.isSafeInteger(Number(key.value)) || String(Number(key.value)) !== key.value) throw new Error('整数记录键必须是规范安全整数')
  } else if (!uuidPattern.test(key.value)) throw new Error('UUID 记录键必须是小写标准格式')
  return key
}

export function encodeUtf8Base64url(value: string): string {
  validUnicode(value)
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '')
}

function decodeUtf8Base64url(encoded: string): string {
  if (!/^[A-Za-z0-9_-]+$/.test(encoded) || encoded.length % 4 === 1) throw new Error('记录键编码无效')
  const padding = '='.repeat((4 - encoded.length % 4) % 4)
  let binary: string
  try { binary = atob(encoded.replaceAll('-', '+').replaceAll('_', '/') + padding) } catch { throw new Error('记录键编码无效') }
  const bytes = Uint8Array.from(binary, character => character.charCodeAt(0))
  let value: string
  try { value = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes) } catch { throw new Error('记录键不是有效 UTF-8') }
  if (encodeUtf8Base64url(value) !== encoded) throw new Error('记录键编码不规范')
  return value
}

export function encodeRecordKey(key: RecordKey): string {
  return encodeUtf8Base64url(validateRecordKey(key).value)
}

export function decodeRecordKey(type: RecordKey['type'], encoded: string): RecordKey {
  return validateRecordKey({ type, value: decodeUtf8Base64url(encoded) } as RecordKey)
}
