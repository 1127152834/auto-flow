import { getPinyin } from './pinyin'

const KEY = /^[A-Za-z_一-龥][A-Za-z0-9_一-龥]{0,63}$/

/** English key suggestion from a (Chinese) name; the key is a stable identity, not shown outside "高级". */
export function suggestKey(name: string, taken: readonly string[], fallback = 'field'): string {
  let base = getPinyin(name.trim()).replace(/[^a-z0-9]/g, '').slice(0, 40)
  if (/^\d/.test(base)) base = `${fallback}${base}`
  const used = new Set(taken)
  if (base) {
    for (let n = 1; ; n++) { const key = n === 1 ? base : `${base}${n}`; if (!used.has(key)) return key }
  }
  for (let n = 1; ; n++) if (!used.has(`${fallback}${n}`)) return `${fallback}${n}`
}

export interface TableFieldLike { key: string; name: string; type: string; required: boolean }
export interface ImportCandidate { key: string; name: string; type: string; required: boolean; exists: boolean }

/** Signature fields a data table could provide; fields whose key is already in the group are marked, not duplicated. */
export function importCandidates(fields: readonly TableFieldLike[], existingKeys: readonly string[]): ImportCandidate[] {
  const taken = [...existingKeys]
  return fields.map(field => {
    const exists = existingKeys.includes(field.key)
    const key = exists || KEY.test(field.key) && !taken.includes(field.key) ? field.key : suggestKey(field.name, taken)
    taken.push(key)
    return { key, name: field.name, type: field.type, required: field.required, exists }
  })
}
