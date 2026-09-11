import { describe, expect, it } from 'vitest'
import type { InstalledKernel, ProfileRead, ProxyOptionsRead } from '../../shared/api/types'
import {
  createProfileFormSchema,
  emptyProfileForm,
  profileFormSchema,
  toForm,
  toWrite,
} from './form-schema'

const installedKernels: InstalledKernel[] = [
  { edition: 'public', version: '146.0.1.0', executablePath: '/kernels/public', size: 1 },
  { edition: 'licensed', version: '146.0.1.1', executablePath: '/kernels/licensed', size: 1 },
]
const proxyOptions: ProxyOptionsRead = {
  proxies: [
    { id: 'proxy-1', name: '上海代理', enabled: true },
    { id: 'proxy-disabled', name: '失效代理', enabled: false },
  ],
  pools: [{ id: 'pool-1', name: '默认代理池' }],
}
const schema = createProfileFormSchema({ installedKernels, proxyOptions })

function validForm() {
  return { ...emptyProfileForm, name: '工作环境', browserKernel: 'public|146.0.1.0' }
}

describe('profile form schema', () => {
  it('requires a real installed kernel selection', () => {
    expect(profileFormSchema.safeParse({ ...emptyProfileForm, browserKernel: '' }).success).toBe(false)
    expect(schema.safeParse({ ...validForm(), browserKernel: 'public|missing' }).success).toBe(false)
    expect(schema.safeParse(validForm()).success).toBe(true)
  })

  it('counts names by Unicode code point and trims them', () => {
    expect(schema.parse({ ...validForm(), name: `  ${'中'.repeat(120)}  ` }).name).toHaveLength(120)
    expect(schema.safeParse({ ...validForm(), name: '😀'.repeat(120) }).success).toBe(true)
    expect(schema.safeParse({ ...validForm(), name: '😀'.repeat(121) }).success).toBe(false)
  })

  it.each([
    ['about:blank', true],
    ['https://example.com/path?q=1', true],
    ['http://localhost:3000', true],
    ['http:', false],
    ['ftp://example.com', false],
    ['http://example.com:bad', false],
  ])('validates start URL %s', (startUrl, accepted) => {
    expect(schema.safeParse({ ...validForm(), startUrl }).success).toBe(accepted)
  })

  it.each(['en', 'en-US', 'zh-Hans-CN', 'en-a-aaa', 'x-private', 'de-CH-1901', 'i-klingon'])(
    'accepts backend-compatible BCP 47 locale %s',
    (locale) => expect(schema.safeParse({ ...validForm(), locale }).success).toBe(true),
  )

  it.each(['en-US-GB', 'en-a', 'x', 'en-a-aaa-a-bbb', 'en-variant-variant', 'en--US'])(
    'rejects malformed BCP 47 locale %s',
    (locale) => expect(schema.safeParse({ ...validForm(), locale }).success).toBe(false),
  )

  it('validates timezone and viewport boundaries', () => {
    expect(schema.safeParse({ ...validForm(), timezone: 'Asia/Shanghai', viewportWidth: '320', viewportHeight: '4320' }).success).toBe(true)
    expect(schema.safeParse({ ...validForm(), timezone: 'Mars/Olympus' }).success).toBe(false)
    expect(schema.safeParse({ ...validForm(), viewportWidth: '319' }).success).toBe(false)
    expect(schema.safeParse({ ...validForm(), viewportHeight: '4321' }).success).toBe(false)
    expect(schema.safeParse({ ...validForm(), viewportWidth: '320.5' }).success).toBe(false)
  })

  it.each([
    '--proxy-server=http://localhost',
    '--proxy-server http://localhost',
    '--user-data-dir /tmp/profile',
    '--fingerprint=42',
    '--remote-debugging-address 127.0.0.1',
    '--remote-debugging-port=9222',
    '--load-extension /tmp/extension',
  ])('rejects reserved Chromium argument %s', (argument) => {
    expect(schema.safeParse({ ...validForm(), expertArgsText: argument }).success).toBe(false)
  })

  it('requires the selected proxy resource to exist and be usable', () => {
    expect(schema.safeParse({ ...validForm(), proxyMode: 'proxy', proxyId: '' }).success).toBe(false)
    expect(schema.safeParse({ ...validForm(), proxyMode: 'proxy', proxyId: 'proxy-disabled' }).success).toBe(false)
    expect(schema.safeParse({ ...validForm(), proxyMode: 'proxy', proxyId: 'proxy-1' }).success).toBe(true)
    expect(schema.safeParse({ ...validForm(), proxyMode: 'pool', proxyPoolId: 'missing' }).success).toBe(false)
    expect(schema.safeParse({ ...validForm(), proxyMode: 'pool', proxyPoolId: 'pool-1' }).success).toBe(true)
  })
})

describe('profile wire conversion', () => {
  it('round-trips every writable field without exposing server-owned fields', () => {
    const profile: ProfileRead = {
      id: '67c727cd-b0d9-4f0f-8618-aec4e8a7d0ff',
      fingerprintSeed: 12345,
      createdAt: '2026-09-12T00:00:00Z',
      updatedAt: '2026-09-12T01:00:00Z',
      name: '工作环境',
      description: '说明',
      startUrl: 'https://example.com',
      locale: 'zh-Hans-CN',
      timezone: 'Asia/Shanghai',
      geoip: true,
      headless: true,
      humanize: true,
      humanPreset: 'careful',
      userAgent: 'Custom UA',
      viewportJson: { width: 1536, height: 864 },
      colorScheme: 'dark',
      extensionPathsJson: ['/one', '/two'],
      expertArgsJson: ['--disable-notifications', '--window-position=40,40'],
      browserVersion: '146.0.1.1',
      browserEdition: 'licensed',
      releaseChannel: 'preview',
      proxyMode: 'pool',
      proxyId: null,
      proxyPoolId: 'pool-1',
    }

    const form = toForm(profile)
    expect(form).not.toHaveProperty('id')
    expect(form).not.toHaveProperty('fingerprintSeed')
    expect(toWrite(schema.parse(form))).toEqual({
      name: profile.name,
      description: profile.description,
      startUrl: profile.startUrl,
      locale: profile.locale,
      timezone: profile.timezone,
      geoip: profile.geoip,
      headless: profile.headless,
      humanize: profile.humanize,
      humanPreset: profile.humanPreset,
      userAgent: profile.userAgent,
      viewportJson: profile.viewportJson,
      colorScheme: profile.colorScheme,
      extensionPathsJson: profile.extensionPathsJson,
      expertArgsJson: profile.expertArgsJson,
      browserVersion: profile.browserVersion,
      browserEdition: profile.browserEdition,
      releaseChannel: profile.releaseChannel,
      proxyMode: profile.proxyMode,
      proxyId: profile.proxyId,
      proxyPoolId: profile.proxyPoolId,
    })
  })

  it('normalizes public channel, mutually exclusive proxy IDs, empty optionals, and text lines', () => {
    expect(toWrite({
      ...validForm(),
      name: '  工作环境  ',
      locale: '',
      timezone: '',
      userAgent: '',
      colorScheme: '',
      releaseChannel: 'preview',
      proxyMode: 'proxy',
      proxyId: 'proxy-1',
      proxyPoolId: 'stale-pool',
      extensionPathsText: ' /one \r\n\n /two ',
      expertArgsText: ' --disable-notifications \n\n --window-position=40,40 ',
    })).toEqual(expect.objectContaining({
      name: '工作环境',
      locale: null,
      timezone: null,
      userAgent: null,
      colorScheme: null,
      releaseChannel: 'stable',
      proxyId: 'proxy-1',
      proxyPoolId: null,
      extensionPathsJson: ['/one', '/two'],
      expertArgsJson: ['--disable-notifications', '--window-position=40,40'],
    }))
  })
})
