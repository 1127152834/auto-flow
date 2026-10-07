/**
 * 前端实验开关：不在设置界面暴露，仅供灰度、CI 与 QA 使用。
 * 优先级：URL 参数（?flag.<名称>=1）> 构建环境变量 > localStorage > 默认关闭。
 */
const FLAGS = {
  newStudioLayout: { storageKey: 'autoflow.flags.newStudioLayout', env: 'VITE_FLAG_NEW_STUDIO_LAYOUT' },
  tagInput: { storageKey: 'autoflow.flags.tagInput', env: 'VITE_FLAG_TAG_INPUT' },
} as const

export type FlagName = keyof typeof FLAGS

const parse = (raw: string | null | undefined): boolean | null => {
  if (raw === 'true' || raw === '1') return true
  if (raw === 'false' || raw === '0') return false
  return null
}

export function isEnabled(name: FlagName): boolean {
  const { storageKey, env } = FLAGS[name]
  try {
    const fromUrl = parse(new URLSearchParams(window.location.search).get(`flag.${name}`))
    if (fromUrl !== null) return fromUrl
  } catch { /* 无 window 或地址不可读时忽略 */ }
  const fromEnv = parse((import.meta.env as Record<string, string | undefined>)[env])
  if (fromEnv !== null) return fromEnv
  try {
    return parse(localStorage.getItem(storageKey)) === true
  } catch {
    return false
  }
}

export function setFlag(name: FlagName, on: boolean): void {
  try {
    localStorage.setItem(FLAGS[name].storageKey, on ? 'true' : 'false')
  } catch { /* 存储不可用时开关保持默认 */ }
}

export function clearFlag(name: FlagName): void {
  try {
    localStorage.removeItem(FLAGS[name].storageKey)
  } catch { /* 同上 */ }
}
