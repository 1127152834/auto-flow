import { z } from 'zod'
import type {
  InstalledKernel,
  KernelRef,
  ProfileRead,
  ProfileWrite,
  ProxyOptionsRead,
} from '../../shared/api/types'
import { getViewportPreset } from './presets'

const GRANDFATHERED_LOCALES = new Set([
  'art-lojban', 'cel-gaulish', 'en-gb-oed', 'i-ami', 'i-bnn', 'i-default', 'i-enochian',
  'i-hak', 'i-klingon', 'i-lux', 'i-mingo', 'i-navajo', 'i-pwn', 'i-tao', 'i-tay',
  'i-tsu', 'no-bok', 'no-nyn', 'sgn-be-fr', 'sgn-be-nl', 'sgn-ch-de', 'zh-guoyu',
  'zh-hakka', 'zh-min', 'zh-min-nan', 'zh-xiang',
])
const FORBIDDEN_ARGUMENTS = new Set([
  '--user-data-dir',
  '--fingerprint',
  '--remote-debugging-address',
  '--remote-debugging-port',
  '--proxy-server',
  '--load-extension',
])

function isBcp47(tag: string): boolean {
  if (GRANDFATHERED_LOCALES.has(tag.toLowerCase())) return true
  const parts = tag.split('-')
  if (parts.some((part) => !part || part.length > 8 || !/^[A-Za-z0-9]+$/.test(part))) return false
  if (parts[0]?.toLowerCase() === 'x') return parts.length > 1

  const language = parts[0] ?? ''
  if (!/^[A-Za-z]+$/.test(language) || language.length < 2 || language.length > 8) return false
  let index = 1
  if (language.length <= 3) {
    for (let count = 0; count < 3; count += 1) {
      const part = parts[index]
      if (part?.length === 3 && /^[A-Za-z]+$/.test(part)) index += 1
      else break
    }
  }
  if (parts[index]?.length === 4 && /^[A-Za-z]+$/.test(parts[index])) index += 1
  const region = parts[index]
  if (region && ((region.length === 2 && /^[A-Za-z]+$/.test(region)) || (region.length === 3 && /^\d+$/.test(region)))) index += 1

  const variants = new Set<string>()
  while (index < parts.length) {
    const part = parts[index]
    if (!part || !((part.length >= 5 && part.length <= 8) || (part.length === 4 && /^\d/.test(part)))) break
    const variant = part.toLowerCase()
    if (variants.has(variant)) return false
    variants.add(variant)
    index += 1
  }

  const extensions = new Set<string>()
  while (index < parts.length && parts[index]?.length === 1 && parts[index]?.toLowerCase() !== 'x') {
    const singleton = parts[index]!.toLowerCase()
    if (extensions.has(singleton)) return false
    extensions.add(singleton)
    index += 1
    const start = index
    while (index < parts.length && parts[index]!.length >= 2 && parts[index]!.length <= 8) index += 1
    if (index === start) return false
  }

  if (parts[index]?.toLowerCase() === 'x') {
    index += 1
    if (index === parts.length) return false
    index = parts.length
  }
  return index === parts.length
}

function isTimezone(value: string): boolean {
  if (!value) return true
  try {
    new Intl.DateTimeFormat('zh-CN', { timeZone: value }).format()
    return true
  } catch {
    return false
  }
}

function isStartUrl(value: string): boolean {
  if (value === 'about:blank') return true
  if (!/^https?:\/\/[^/]/i.test(value)) return false
  try {
    const url = new URL(value)
    return (url.protocol === 'http:' || url.protocol === 'https:') && Boolean(url.hostname)
  } catch {
    return false
  }
}

function isViewportDimension(value: string, min: number, max: number) {
  const number = Number(value)
  return Number.isInteger(number) && number >= min && number <= max
}

const profileFormFields = z.object({
  name: z.string().trim().min(1, '请输入名称').refine((value) => [...value].length <= 120, '名称最多 120 个字符'),
  description: z.string(),
  startUrl: z.string().trim().refine(isStartUrl, '请输入有效的 HTTP/HTTPS 地址，或使用 about:blank'),
  locale: z.string().trim().refine((value) => !value || isBcp47(value), '请输入有效的 BCP 47 语言标记，例如 zh-CN'),
  timezone: z.string().trim().refine(isTimezone, '请输入有效的 IANA 时区，例如 Asia/Shanghai'),
  headless: z.boolean(),
  geoip: z.boolean(),
  humanize: z.boolean(),
  humanPreset: z.enum(['default', 'careful']),
  userAgent: z.string(),
  viewportMode: z.enum(['browser', 'preset', 'custom']),
  viewportWidth: z.string(),
  viewportHeight: z.string(),
  colorScheme: z.enum(['', 'light', 'dark', 'no-preference']),
  browserKernel: z.string().min(1, '请选择浏览器内核'),
  releaseChannel: z.enum(['stable', 'preview']),
  extensionPathsText: z.string(),
  expertArgsText: z.string(),
  proxyMode: z.enum(['none', 'proxy', 'pool']),
  proxyId: z.string(),
  proxyPoolId: z.string(),
})

export type ProfileFormValues = z.infer<typeof profileFormFields>

export const emptyProfileForm: ProfileFormValues = {
  name: '',
  description: '',
  startUrl: 'about:blank',
  locale: 'zh-CN',
  timezone: 'Asia/Shanghai',
  headless: false,
  geoip: false,
  humanize: false,
  humanPreset: 'default',
  userAgent: '',
  viewportMode: 'preset',
  viewportWidth: '1280',
  viewportHeight: '800',
  colorScheme: '',
  browserKernel: '',
  releaseChannel: 'stable',
  extensionPathsText: '',
  expertArgsText: '',
  proxyMode: 'none',
  proxyId: '',
  proxyPoolId: '',
}

export type ProfileFormResources = {
  installedKernels: readonly InstalledKernel[]
  proxyOptions: ProxyOptionsRead
}

export function kernelKey(kernel: Pick<InstalledKernel, 'edition' | 'version'>): string {
  return `${kernel.edition}|${kernel.version}`
}

export function parseKernelKey(value: string): KernelRef | null {
  const [edition, version, extra] = value.split('|')
  if (extra !== undefined || !version || (edition !== 'public' && edition !== 'licensed')) return null
  return { edition, version }
}

export function createProfileFormSchema(resources: ProfileFormResources) {
  return profileFormFields.superRefine((values, context) => {
    if (values.viewportMode !== 'browser') {
      if (!isViewportDimension(values.viewportWidth, 320, 7680)) {
        context.addIssue({ code: 'custom', path: ['viewportWidth'], message: '视口宽度必须是 320–7680 之间的整数' })
      }
      if (!isViewportDimension(values.viewportHeight, 240, 4320)) {
        context.addIssue({ code: 'custom', path: ['viewportHeight'], message: '视口高度必须是 240–4320 之间的整数' })
      }
    }
    const kernel = parseKernelKey(values.browserKernel)
    if (values.browserKernel && (!kernel || !resources.installedKernels.some((item) => kernelKey(item) === values.browserKernel))) {
      context.addIssue({ code: 'custom', path: ['browserKernel'], message: '所选浏览器内核已不可用，请重新选择' })
    }
    if (kernel?.edition === 'public' && values.releaseChannel !== 'stable') {
      context.addIssue({ code: 'custom', path: ['releaseChannel'], message: '公开版仅支持 Stable 发布通道' })
    }

    if (values.proxyMode === 'proxy') {
      if (!values.proxyId) context.addIssue({ code: 'custom', path: ['proxyId'], message: '请选择代理' })
      else if (!resources.proxyOptions.proxies.some((item) => item.id === values.proxyId && item.enabled)) {
        context.addIssue({ code: 'custom', path: ['proxyId'], message: '所选代理已不可用，请重新选择' })
      }
    }
    if (values.proxyMode === 'pool') {
      if (!values.proxyPoolId) context.addIssue({ code: 'custom', path: ['proxyPoolId'], message: '请选择代理池' })
      else if (!resources.proxyOptions.pools.some((item) => item.id === values.proxyPoolId)) {
        context.addIssue({ code: 'custom', path: ['proxyPoolId'], message: '所选代理池已不可用，请重新选择' })
      }
    }

    for (const argument of splitLines(values.expertArgsText)) {
      const normalized = argument.split(/\s+/, 1)[0]!.split('=', 1)[0]!
      if (FORBIDDEN_ARGUMENTS.has(normalized)) {
        context.addIssue({ code: 'custom', path: ['expertArgsText'], message: `AutoFlow 已管理 ${normalized}，请移除此参数` })
        break
      }
    }
  })
}

export const profileFormSchema = createProfileFormSchema({
  installedKernels: [],
  proxyOptions: { proxies: [], pools: [] },
})

function splitLines(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

export function toForm(profile: ProfileRead): ProfileFormValues {
  return {
    ...emptyProfileForm,
    name: profile.name,
    description: profile.description,
    startUrl: profile.startUrl,
    locale: profile.locale ?? '',
    timezone: profile.timezone ?? '',
    headless: profile.headless,
    geoip: profile.geoip,
    humanize: profile.humanize,
    humanPreset: profile.humanPreset,
    userAgent: profile.userAgent ?? '',
    viewportMode: profile.viewportJson
      ? getViewportPreset(String(profile.viewportJson.width), String(profile.viewportJson.height)) ? 'preset' : 'custom'
      : 'browser',
    viewportWidth: profile.viewportJson ? String(profile.viewportJson.width) : '',
    viewportHeight: profile.viewportJson ? String(profile.viewportJson.height) : '',
    colorScheme: profile.colorScheme ?? '',
    browserKernel: `${profile.browserEdition}|${profile.browserVersion}`,
    releaseChannel: profile.browserEdition === 'public' ? 'stable' : profile.releaseChannel,
    extensionPathsText: (profile.extensionPathsJson ?? []).join('\n'),
    expertArgsText: (profile.expertArgsJson ?? []).join('\n'),
    proxyMode: profile.proxyMode,
    proxyId: profile.proxyId ?? '',
    proxyPoolId: profile.proxyPoolId ?? '',
  }
}

export function toWrite(values: ProfileFormValues): ProfileWrite {
  const kernel = parseKernelKey(values.browserKernel)
  return {
    name: values.name.trim(),
    description: values.description,
    startUrl: values.startUrl.trim(),
    locale: values.locale.trim() || null,
    timezone: values.timezone.trim() || null,
    geoip: values.geoip,
    headless: values.headless,
    humanize: values.humanize,
    humanPreset: values.humanPreset,
    userAgent: values.userAgent || null,
    viewportJson: values.viewportMode === 'browser'
      ? null
      : { width: Number(values.viewportWidth), height: Number(values.viewportHeight) },
    colorScheme: values.colorScheme || null,
    extensionPathsJson: splitLines(values.extensionPathsText),
    expertArgsJson: splitLines(values.expertArgsText),
    browserVersion: kernel?.version ?? '',
    browserEdition: kernel?.edition ?? 'public',
    releaseChannel: kernel?.edition === 'licensed' ? values.releaseChannel : 'stable',
    proxyMode: values.proxyMode,
    proxyId: values.proxyMode === 'proxy' ? values.proxyId : null,
    proxyPoolId: values.proxyMode === 'pool' ? values.proxyPoolId : null,
  }
}
